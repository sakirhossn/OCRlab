"""Model Context Protocol (MCP) Server for Unlimited OCR Cloud.

Enables AI coding agents (Claude Desktop, Cursor, Gemini) to invoke OCR tools
for reading PDFs, extracting tables, and obtaining structured document data.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unlimited_ocr import UnlimitedOCRClient, wrap_untrusted_ocr_text

API_KEY = os.getenv("UNLIMITED_OCR_API_KEY", "")
BASE_URL = os.getenv("UNLIMITED_OCR_BASE_URL", "https://api.ocrlab.cloud/v1")


def get_client() -> UnlimitedOCRClient:
    if not API_KEY:
        raise ValueError("UNLIMITED_OCR_API_KEY environment variable is required.")
    return UnlimitedOCRClient(api_key=API_KEY, base_url=BASE_URL)


# MCP Tool Definitions
TOOLS = [
    {
        "name": "ocr_parse_document",
        "description": "Uploads and converts a local PDF or image file into structured Markdown and JSON using Baidu Unlimited-OCR-2 and PyMuPDF.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute or relative path to the local PDF, PNG, or JPEG file"},
                "mode": {"type": "string", "enum": ["auto", "native_only", "ocr_only"], "default": "auto", "description": "Extraction mode"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "ocr_check_job_status",
        "description": "Checks the current processing status and progress percentage of an OCR job.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "The unique job identifier returned by upload"}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "ocr_get_result",
        "description": "Retrieves the parsed document content in requested format (markdown, json, or text).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "The unique job identifier"},
                "format": {"type": "string", "enum": ["markdown", "json", "text"], "default": "markdown"}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "ocr_get_usage",
        "description": "Inspects remaining monthly page quota and tier limits for the current API key.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    client = get_client()

    if tool_name == "ocr_parse_document":
        file_path = Path(arguments["file_path"])
        if not file_path.is_file():
            return {"error": f"File not found: {file_path}"}

        file_bytes = file_path.read_bytes()
        mode = arguments.get("mode", "auto")

        upload_resp = client.upload_document(file_bytes=file_bytes, filename=file_path.name, mode=mode)
        job_id = upload_resp.job_id

        # Wait for completion
        status = client.wait_for_completion(job_id, timeout=90.0)
        if status.status != "succeeded":
            return {"error": f"OCR processing failed with status '{status.status}': {status.error_message}"}

        # Fetch Markdown and JSON
        markdown = client.get_result_markdown(job_id)
        contract = client.get_result_json(job_id)

        # Wrap in prompt defense tags before returning to agent context
        safe_markdown = wrap_untrusted_ocr_text(markdown)

        return {
            "status": "succeeded",
            "job_id": job_id,
            "document_id": contract.document_id,
            "page_count": contract.page_count,
            "engine": contract.engine,
            "markdown": safe_markdown,
            "raw_contract": contract.model_dump(),
        }

    elif tool_name == "ocr_check_job_status":
        status = client.get_job_status(arguments["job_id"])
        return status.model_dump()

    elif tool_name == "ocr_get_result":
        job_id = arguments["job_id"]
        fmt = arguments.get("format", "markdown")
        if fmt == "json":
            return client.get_result_json(job_id).model_dump()
        elif fmt == "text":
            return {"text": client.get_result_text(job_id)}
        else:
            return {"markdown": client.get_result_markdown(job_id)}

    elif tool_name == "ocr_get_usage":
        usage = client.get_usage()
        return usage.model_dump()

    else:
        return {"error": f"Unknown tool: {tool_name}"}


def main():
    """Standard JSON-RPC loop for Model Context Protocol."""
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                res = handle_tool_call(name, args)
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}}
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
