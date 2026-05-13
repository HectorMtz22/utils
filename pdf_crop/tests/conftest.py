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
