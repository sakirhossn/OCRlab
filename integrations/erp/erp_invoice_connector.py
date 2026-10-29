"""Generic Enterprise Resource Planning (ERP) & Accounting Connector.

Demonstrates the real production flow:
Existing Application -> Upload PDF -> Save Job ID -> Receive Webhook ->
Fetch Structured JSON -> Validate and Map Fields -> Save to ERP Database.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional
from unlimited_ocr import UnlimitedOCRClient, verify_webhook_signature


class ERPDatabase:
    """Simulates an existing corporate accounting / ERP SQL database."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS erp_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_job_id TEXT UNIQUE,
                    vendor_name TEXT,
                    invoice_number TEXT,
                    total_amount REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS erp_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER,
                    description TEXT,
                    quantity REAL,
                    unit_price REAL,
                    total_amount REAL,
                    FOREIGN KEY(invoice_id) REFERENCES erp_invoices(id)
                );
            """)

    def record_pending_invoice(self, job_id: str, filename: str) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO erp_invoices (external_job_id, vendor_name, status) VALUES (?, ?, ?)",
                (job_id, f"Pending ({filename})", "PENDING_OCR"),
            )
            return cursor.lastrowid

    def commit_parsed_invoice(
        self,
        job_id: str,
        vendor_name: str,
        invoice_number: str,
        total_amount: float,
        line_items: List[Dict[str, Any]],
    ):
        with self.conn:
            # 1. Update invoice master
            cursor = self.conn.execute(
                """
                UPDATE erp_invoices
                SET vendor_name = ?, invoice_number = ?, total_amount = ?, status = 'PROCESSED'
                WHERE external_job_id = ?
                """,
                (vendor_name, invoice_number, total_amount, job_id),
            )
            # Fetch invoice ID
            cursor = self.conn.execute(
                "SELECT id FROM erp_invoices WHERE external_job_id = ?", (job_id,)
            )
            invoice_id = cursor.fetchone()[0]

            # 2. Insert line items
            for item in line_items:
                self.conn.execute(
                    """
                    INSERT INTO erp_line_items (invoice_id, description, quantity, unit_price, total_amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id,
                        item.get("description", "Unknown Item"),
                        item.get("quantity", 1.0),
                        item.get("unit_price", 0.0),
                        item.get("total", 0.0),
                    ),
                )


class ERPConnector:
    """Connects external ERP software with Unlimited OCR Cloud."""

    def __init__(self, api_key: str, webhook_secret: str, base_url: str = "https://api.ocrlab.cloud/v1"):
        self.ocr_client = UnlimitedOCRClient(api_key=api_key, base_url=base_url)
        self.webhook_secret = webhook_secret
        self.erp_db = ERPDatabase()

    def process_incoming_pdf(self, pdf_bytes: bytes, filename: str) -> str:
        """Step 1: Upload document, initiate OCR, record job in ERP."""
        upload_resp = self.ocr_client.upload_document(
            file_bytes=pdf_bytes,
            filename=filename,
            mode="auto",
        )
        job_id = upload_resp.job_id

        # Save reference in ERP database
        self.erp_db.record_pending_invoice(job_id, filename)
        return job_id

    def handle_webhook_notification(
        self,
        headers: Dict[str, str],
        raw_body: bytes,
    ) -> bool:
        """Step 2 & 3: Receive signed webhook, verify HMAC, fetch JSON, map to ERP."""
        # 1. Verify HMAC-SHA256 signature
        if not verify_webhook_signature(self.webhook_secret, headers, raw_body):
            raise PermissionError("Invalid webhook signature or expired timestamp.")

        payload = json.loads(raw_body.decode("utf-8"))
        job_id = payload.get("job_id")
        if not job_id or payload.get("event") != "job.completed":
            return False

        # 2. Fetch structured JSON contract
        contract = self.ocr_client.get_result_json(job_id)

        # 3. Map structured blocks to ERP fields
        line_items: List[Dict[str, Any]] = []
        vendor_name = "Acme Corp Vendor"
        invoice_number = "INV-2026-001"
        total_sum = 0.0

        for page in contract.pages:
            for block in page.blocks:
                # Look for headings to capture invoice numbers or vendor titles
                if block.type == "heading" and "INV-" in (block.text or ""):
                    invoice_number = block.text.strip()

                # Look for tables containing line items
                if block.type == "table" and block.rows:
                    for row in block.rows:
                        if len(row) >= 3:
                            desc = str(row[0])
                            try:
                                qty = float(str(row[1]).replace(",", ""))
                            except ValueError:
                                qty = 1.0
                            try:
                                price = float(str(row[2]).replace("$", "").replace(",", ""))
                            except ValueError:
                                price = 0.0

                            total = round(qty * price, 2)
                            total_sum += total
                            line_items.append({
                                "description": desc,
                                "quantity": qty,
                                "unit_price": price,
                                "total": total,
                            })

        # 4. Save mapped records into ERP database
        self.erp_db.commit_parsed_invoice(
            job_id=job_id,
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            total_amount=round(total_sum, 2),
            line_items=line_items,
        )
        return True
