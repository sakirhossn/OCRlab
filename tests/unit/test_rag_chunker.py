"""Unit tests for the RAG heading-aware vector chunker."""

from integrations.rag.rag_ingestion_chunker import RAGDocumentChunker
from unlimited_ocr.models import DocumentBlock, DocumentPage, StructuredResultContract


def test_rag_chunker_preserves_heading_hierarchy():
    contract = StructuredResultContract(
        schema_version="1.0",
        document_id="doc_rag_101",
        status="succeeded",
        page_count=1,
        engine="unlimited-ocr-2",
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(block_id="b1", type="heading", level=1, text="Company Overview", reading_order=1),
                    DocumentBlock(block_id="b2", type="paragraph", text="We specialize in cloud-native OCR architectures.", reading_order=2),
                    DocumentBlock(block_id="b3", type="heading", level=2, text="Financial Performance", reading_order=3),
                    DocumentBlock(block_id="b4", type="table", headers=["Metric", "FY25"], rows=[["ARR", "$10M"]], reading_order=4),
                ]
            )
        ]
    )

    chunker = RAGDocumentChunker()
    chunks = chunker.chunk_contract(contract, apply_prompt_defense=True)

    assert len(chunks) == 2

    # Chunk 1: Company Overview
    c1 = chunks[0]
    assert c1["section_path"] == "Company Overview"
    assert "Company Overview" in c1["content"]
    assert "cloud-native OCR" in c1["content"]
    assert "<untrusted_document_content>" in c1["content"]

    # Chunk 2: Table under Financial Performance
    c2 = chunks[1]
    assert "Company Overview > Financial Performance" in c2["section_path"]
    assert "| Metric | FY25 |" in c2["content"]
    assert "| ARR | $10M |" in c2["content"]
