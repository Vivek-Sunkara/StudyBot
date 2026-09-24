import io
import re
import fitz
from docx import Document

def clean(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def chunks(text, page=1, size=180, overlap=30):
    words = clean(text).split()
    result = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        value = " ".join(words[start:end]).strip()
        if value:
            result.append({"page": page, "section": "", "content": value})
        if end == len(words):
            break
        start = max(start + 1, end - overlap)
    return result

def extract_document(data, suffix, filename):
    suffix = suffix.lower()
    if suffix == ".pdf":
        doc = fitz.open(stream=data, filetype="pdf")
        result = []
        for i, page in enumerate(doc):
            result.extend(chunks(page.get_text("text"), i + 1))
        doc.close()
        return result
    if suffix == ".docx":
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return chunks(text)
    if suffix in {".txt", ".md"}:
        return chunks(data.decode("utf-8", errors="replace"))
    raise ValueError("Unsupported document type")
