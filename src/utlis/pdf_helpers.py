import PyPDF2

async def read_text_file(file):
    """
    Extract all text from a PDF UploadFile.
    Args:
        file: FastAPI UploadFile (PDF)
    Returns:
        str: All text from the PDF
    """
    pdf_reader = PyPDF2.PdfReader(file.file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text