from docx import Document
from pypdf import PdfReader

from app.services.interfaces import ResumeParserInterface


class ResumeParserService(ResumeParserInterface):
    async def parse(self, filename: str, content: bytes) -> str:
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            return self._parse_pdf(content)
        if lower_name.endswith(".docx"):
            return self._parse_docx(content)
        return content.decode("utf-8", errors="ignore")

    def _parse_pdf(self, content: bytes) -> str:
        from io import BytesIO

        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        return text or "Unable to extract text from PDF."

    def _parse_docx(self, content: bytes) -> str:
        from io import BytesIO

        document = Document(BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        return text or "Unable to extract text from DOCX."
