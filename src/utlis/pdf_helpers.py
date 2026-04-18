import PyPDF2
import asyncio

def _extract_pdf_text(file_obj):
    """
    Synchronous helper to extract text from PDF.
    Args:
        file_obj: File-like object containing PDF data
    Returns:
        str: All text from the PDF
    """
    pdf_reader = PyPDF2.PdfReader(file_obj)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

async def read_pdf_text(file):
    """
    Asynchronously extract all text from a PDF UploadFile without blocking the event loop.
    Args:
        file: FastAPI UploadFile (PDF)
    Returns:
        str: All text from the PDF
    """
    # Offload synchronous PDF parsing to a worker thread
    return await asyncio.to_thread(_extract_pdf_text, file.file)