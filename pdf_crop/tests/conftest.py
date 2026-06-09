from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    create_string_object,
)
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


def _xmp_stream() -> DecodedStreamObject:
    stream = DecodedStreamObject()
    stream.set_data(_XMP_PAYLOAD)
    stream.update({
        NameObject("/Type"): NameObject("/Metadata"),
        NameObject("/Subtype"): NameObject("/XML"),
    })
    return stream


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
    root = writer._root_object

    # /Info: a custom (non-standard) key alongside the reportlab ones.
    info = writer._info.get_object()
    info[NameObject("/CustomCorp")] = create_string_object("internal-only")

    # XMP /Metadata: catalog root and per-page.
    root[NameObject("/Metadata")] = writer._add_object(_xmp_stream())
    writer.pages[0][NameObject("/Metadata")] = writer._add_object(_xmp_stream())

    # Trailer /ID.
    writer._ID = ArrayObject([ByteStringObject(b"id0"), ByteStringObject(b"id1")])

    # /PieceInfo: catalog and per-page.
    root[NameObject("/PieceInfo")] = DictionaryObject()
    writer.pages[0][NameObject("/PieceInfo")] = DictionaryObject()

    # An annotation carrying identifying keys.
    annot = DictionaryObject({
        NameObject("/Subtype"): NameObject("/Text"),
        NameObject("/T"): create_string_object("Annot Author"),
        NameObject("/M"): create_string_object("D:20200101000000Z"),
        NameObject("/Contents"): create_string_object("a private note"),
    })
    writer.pages[0][NameObject("/Annots")] = ArrayObject([writer._add_object(annot)])

    # A /Names tree with an embedded file and JavaScript, plus a named dest
    # and an /OpenAction.
    embedded = DictionaryObject({
        NameObject("/Names"): ArrayObject(
            [create_string_object("secret.txt"), DictionaryObject()]
        )
    })
    javascript = DictionaryObject({
        NameObject("/Names"): ArrayObject(
            [
                create_string_object("js0"),
                DictionaryObject({NameObject("/S"): NameObject("/JavaScript")}),
            ]
        )
    })
    dests = DictionaryObject({
        NameObject("/Names"): ArrayObject(
            [create_string_object("dest0"), ArrayObject()]
        )
    })
    names = DictionaryObject({
        NameObject("/EmbeddedFiles"): writer._add_object(embedded),
        NameObject("/JavaScript"): writer._add_object(javascript),
        NameObject("/Dests"): writer._add_object(dests),
    })
    root[NameObject("/Names")] = writer._add_object(names)
    root[NameObject("/OpenAction")] = DictionaryObject(
        {NameObject("/S"): NameObject("/JavaScript")}
    )

    # Outlines/bookmarks.
    root[NameObject("/Outlines")] = writer._add_object(
        DictionaryObject({NameObject("/Type"): NameObject("/Outlines"),
                          NameObject("/Count"): NumberObject(0)})
    )

    dest = tmp_path / "with_metadata_xmp.pdf"
    with dest.open("wb") as f:
        writer.write(f)
    return dest
