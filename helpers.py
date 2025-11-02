from PyPDF2 import PdfReader
import docx2txt
import tempfile
import os

def extract_text_from_pdf(path_or_stream):
    if hasattr(path_or_stream, "read"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(path_or_stream.read())
        tmp.close()
        path = tmp.name
    else:
        path = path_or_stream
    reader = PdfReader(path)
    text = []
    for p in reader.pages:
        text.append(p.extract_text() or "")
    if 'tmp' in locals():
        os.unlink(path)
    return "\n".join(text)

def extract_text_from_docx(path_or_stream):
    if hasattr(path_or_stream, "read"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        tmp.write(path_or_stream.read())
        tmp.close()
        path = tmp.name
        text = docx2txt.process(path)
        os.unlink(path)
        return text
    else:
        return docx2txt.process(path_or_stream)
