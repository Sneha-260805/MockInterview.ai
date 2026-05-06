import re
import fitz  # PyMuPDF


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return _clean("\n".join(pages))


def extract_from_txt(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return _clean(file_bytes.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file — unsupported encoding")


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return extract_from_pdf(file_bytes)
    if ext == "txt":
        return extract_from_txt(file_bytes)
    raise ValueError(f"Unsupported file type: .{ext}")
