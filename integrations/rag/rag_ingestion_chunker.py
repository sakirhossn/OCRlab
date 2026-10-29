"""Retrieval-Augmented Generation (RAG) Document Chunker.

Converts Unlimited OCR versioned JSON contracts into heading-aware,
contextually enriched chunks for vector database embeddings (Chroma, Pinecone, Qdrant).
"""

from typing import Any, Dict, List
from unlimited_ocr.models import StructuredResultContract
from unlimited_ocr.prompt_defense import wrap_untrusted_ocr_text


class RAGDocumentChunker:
    """Splits structured OCR contracts into semantically coherent vector chunks."""

    def __init__(self, max_chunk_tokens: int = 500):
        self.max_chunk_tokens = max_chunk_tokens

    def chunk_contract(
        self,
        contract: StructuredResultContract,
        apply_prompt_defense: bool = True,
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        current_heading_path: List[str] = []
        current_chunk_text: List[str] = []
        current_page = 1

        for page in contract.pages:
            current_page = page.page_number
            for block in page.blocks:
                # 1. Heading Block: updates hierarchy path and creates natural boundary
                if block.type == "heading":
                    if current_chunk_text:
                        chunks.append(self._finalize_chunk(
                            contract.document_id,
                            current_page,
                            current_heading_path,
                            "\n\n".join(current_chunk_text),
                            apply_prompt_defense,
                        ))
                        current_chunk_text = []

                    level = block.level or 1
                    # Trim heading path to current level
                    current_heading_path = current_heading_path[: level - 1]
                    current_heading_path.append(block.text or "Untitled Section")

                # 2. Table Block: preserve intact as GitHub-Flavored Markdown table
                elif block.type == "table":
                    if current_chunk_text:
                        chunks.append(self._finalize_chunk(
                            contract.document_id,
                            current_page,
                            current_heading_path,
                            "\n\n".join(current_chunk_text),
                            apply_prompt_defense,
                        ))
                        current_chunk_text = []

                    tbl_md = []
                    if block.headers:
                        tbl_md.append("| " + " | ".join(block.headers) + " |")
                        tbl_md.append("| " + " | ".join(["---"] * len(block.headers)) + " |")
                    if block.rows:
                        for row in block.rows:
                            tbl_md.append("| " + " | ".join(str(c) for c in row) + " |")

                    table_text = "\n".join(tbl_md)
                    chunks.append(self._finalize_chunk(
                        contract.document_id,
                        current_page,
                        current_heading_path,
                        table_text,
                        apply_prompt_defense,
                    ))

                # 3. List or Formula Block
                elif block.type in ("list", "formula"):
                    current_chunk_text.append(block.text or "")

                # 4. Paragraph Block
                elif block.text:
                    current_chunk_text.append(block.text)

        # Finalize remaining text
        if current_chunk_text:
            chunks.append(self._finalize_chunk(
                contract.document_id,
                current_page,
                current_heading_path,
                "\n\n".join(current_chunk_text),
                apply_prompt_defense,
            ))

        return chunks

    def _finalize_chunk(
        self,
        document_id: str,
        page_number: int,
        heading_path: List[str],
        content: str,
        apply_prompt_defense: bool,
    ) -> Dict[str, Any]:
        path_str = " > ".join(heading_path) if heading_path else "General"
        header_context = f"Context: {path_str}\n\n"
        final_text = header_context + content

        if apply_prompt_defense:
            final_text = wrap_untrusted_ocr_text(final_text)

        return {
            "document_id": document_id,
            "page_number": page_number,
            "section_path": path_str,
            "content": final_text,
            "metadata": {
                "source": "unlimited-ocr-2",
                "page": page_number,
                "section": path_str,
            },
        }
