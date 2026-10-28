"""PDF text extraction with PyMuPDF (fitz).

Only text is read. Images are never OCR'd here: a scanned report produces a
clear Arabic error explaining that OCR would be required, rather than a
silently empty result.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.extraction import PdfValidationError, PdfValidationResult

try:  # pragma: no cover - import guard
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]


MIN_TEXT_CHARS_PER_DOC = 40


@dataclass(frozen=True)
class PdfText:
    page_texts: list[str]
    page_count: int
    encrypted: bool = False

    @property
    def total_chars(self) -> int:
        return sum(len(t.strip()) for t in self.page_texts)


class PdfExtractionError(Exception):
    def __init__(self, error: PdfValidationError, message_ar: str) -> None:
        super().__init__(message_ar)
        self.error = error
        self.message_ar = message_ar


def extract_page_texts(data: bytes) -> PdfText:
    """Extract text per page. Raises PdfExtractionError with an Arabic message."""
    if fitz is None:  # pragma: no cover
        raise PdfExtractionError(
            PdfValidationError.NO_TEXT,
            "مكتبة قراءة ملفات PDF غير مثبتة على الخادم. راجع إعداد الخادم (PyMuPDF).",
        )
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfExtractionError(
            PdfValidationError.NOT_PDF,
            "تعذّر فتح الملف. قد يكون تالفًا أو ليس ملف PDF صالحًا.",
        ) from None

    try:
        if doc.needs_pass:
            raise PdfExtractionError(
                PdfValidationError.ENCRYPTED,
                "الملف محمي بكلمة مرور ولا يمكن قراءته. صدّر التقرير بدون حماية ثم أعد المحاولة.",
            )
        page_texts = [page.get_text("text") or "" for page in doc]
        count = doc.page_count
    finally:
        doc.close()

    result = PdfText(page_texts=page_texts, page_count=count)
    if result.total_chars < MIN_TEXT_CHARS_PER_DOC:
        raise PdfExtractionError(
            PdfValidationError.NO_TEXT,
            "لا يحتوي الملف على نص يمكن قراءته — يبدو أنه تقرير ممسوح ضوئيًا (صور). "
            "قراءة هذا النوع تحتاج إلى تقنية OCR وهي غير مفعّلة في هذا النموذج الأولي. "
            "جرّب تصدير التقرير من تطبيق الحساس كملف PDF نصي.",
        )
    return result


def validation_result_for(err: PdfExtractionError) -> PdfValidationResult:
    return PdfValidationResult(err.error, err.message_ar)
