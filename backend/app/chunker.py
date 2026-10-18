from pydantic import BaseModel

from backend.app.document_processor import ProcessedDocument


class DocumentChunk(BaseModel):
    text: str
    metadata: dict[str, str | int]


def chunk_text(
    text: str,
    filename: str,
    chunk_size: int = 800,
    overlap: int = 120,
    page_number: int | None = None,
    start_index: int = 0,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size.")
    if not text.strip():
        return []

    chunks: list[DocumentChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_value = text[start:end].strip()
        if chunk_value:
            metadata: dict[str, str | int] = {
                "filename": filename,
                "chunk_index": start_index + len(chunks),
            }
            if page_number is not None:
                metadata["page_number"] = page_number
            chunks.append(DocumentChunk(text=chunk_value, metadata=metadata))

        if end == len(text):
            break
        start = end - overlap

    return chunks


def chunk_document(
    document: ProcessedDocument,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[DocumentChunk]:
    if document.pages:
        chunks: list[DocumentChunk] = []
        for page in document.pages:
            chunks.extend(
                chunk_text(
                    page.text,
                    document.original_filename,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    page_number=page.page_number,
                    start_index=len(chunks),
                )
            )
        return chunks

    return chunk_text(
        document.extracted_text,
        document.original_filename,
        chunk_size=chunk_size,
        overlap=overlap,
    )