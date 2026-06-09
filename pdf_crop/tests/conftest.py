import io
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfgen.canvas import Canvas


def _make_pdf(path: Path, page_count: int) -> Path:
    """Generate a minimal PDF with `page_count` pages, each labelled 'Page N'."""
    c = Canvas(str(path))
    for i in range(1, page_count + 1):
        c.setFont("Helvetica", 24)
        c.drawString(72, 720, f"Page {i}")
        c.showPage()
    c.save()
    return path


_XMP_PAYLOAD = b"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Secret Title</rdf:li></rdf:Alt></dc:title>
<dc:creator><rdf:Seq><rdf:li>Secret Author</rdf:li></rdf:Seq></dc:creator>
</rdf:Description>
</rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


@pytest.fixture
def pdf_factory(tmp_path):
    """Returns a callable: pdf_factory(name, pages) -> Path."""
    def _factory(name: str, page_count: int) -> Path:
        return _make_pdf(tmp_path / name, page_count)
    return _factory


@pytest.fixture
def three_page_pdf(pdf_factory):
    return pdf_factory("three.pdf", 3)


@pytest.fixture
def ten_page_pdf(pdf_factory):
    return pdf_factory("ten.pdf", 10)


@pytest.fixture
def text_pdf_factory(tmp_path):
    """PDF with one line of text per page. text_pdf_factory(["line a", "line b"]) -> Path."""
    def _factory(lines):
        path = tmp_path / "text.pdf"
        c = Canvas(str(path))
        for line in lines:
            c.setFont("Helvetica", 12)
            c.drawString(72, 720, line)
            c.showPage()
        c.save()
        return path
    return _factory


@pytest.fixture
def qr_pdf_factory(tmp_path):
    """PDF with one QR code per page. qr_pdf_factory(["payload a", ...]) -> Path.

    Each QR is rendered with segno and embedded at a fixed rect via PyMuPDF, so
    the document has a real image layer (not a text layer) for the qr_redact
    feature to find.
    """
    import fitz
    import segno

    def _factory(payloads):
        doc = fitz.open()
        for payload in payloads:
            buf = io.BytesIO()
            segno.make(payload, error="h").save(buf, kind="png", scale=10, border=4)
            page = doc.new_page(width=595, height=842)  # A4
            page.insert_image(fitz.Rect(100, 100, 250, 250), stream=buf.getvalue())
        path = tmp_path / "qr.pdf"
        doc.save(str(path))
        doc.close()
        return path

    return _factory


@pytest.fixture
def pdf_with_metadata(tmp_path) -> Path:
    src = tmp_path / "with_metadata.pdf"
    c = Canvas(str(src))
    c.setTitle("Secret Title")
    c.setAuthor("Secret Author")
    c.setSubject("Secret Subject")
    c.setKeywords("alpha,beta,gamma")
    for i in range(1, 4):
        c.setFont("Helvetica", 24)
        c.drawString(72, 720, f"Page {i}")
        c.showPage()
    c.save()

    reader = PdfReader(str(src))
    writer = PdfWriter(clone_from=reader)
    stream = DecodedStreamObject()
    stream.set_data(_XMP_PAYLOAD)
    stream.update({
        NameObject("/Type"): NameObject("/Metadata"),
        NameObject("/Subtype"): NameObject("/XML"),
    })
    ref = writer._add_object(stream)
    writer._root_object[NameObject("/Metadata")] = ref
    dest = tmp_path / "with_metadata_xmp.pdf"
    with dest.open("wb") as f:
        writer.write(f)
    return dest
