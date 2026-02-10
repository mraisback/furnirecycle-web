import io

from pypdf import PdfReader, PdfWriter

from app import UploadedPdf, merge_pdfs


def make_pdf(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_merge_pdfs_combines_pages_in_order():
    first = UploadedPdf(name="a.pdf", content=make_pdf(1))
    second = UploadedPdf(name="b.pdf", content=make_pdf(2))

    merged = merge_pdfs([first, second])
    reader = PdfReader(merged)

    assert len(reader.pages) == 3
