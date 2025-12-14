import PyPDF2

async def read_text_file(file):
    # file is an UploadFile
    pdf_reader = PyPDF2.PdfReader(file.file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text