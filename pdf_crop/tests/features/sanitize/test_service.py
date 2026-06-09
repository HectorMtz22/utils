from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    create_string_object,
)

from pdf_crop.features.sanitize import service as sanitize_service


def _embedded_files_via_kids(writer):
    """Attach a /Names /EmbeddedFiles name tree that uses intermediate /Kids
    nodes (no top-level /Names leaf), as pypdf/Acrobat produce for large trees.

    Returns the total number of file entries across the leaves.
    """
    root = writer._root_object

    def _leaf(name: str) -> DictionaryObject:
        return DictionaryObject({
            NameObject("/Names"): ArrayObject(
                [create_string_object(name), DictionaryObject()]
            )
        })

    leaf_a = writer._add_object(_leaf("a.txt"))
    leaf_b = writer._add_object(_leaf("b.txt"))
    leaf_c = writer._add_object(_leaf("c.txt"))

    # An intermediate /Kids node nested under the top-level /Kids node, so the
    # tree is two levels deep.
    nested = writer._add_object(
        DictionaryObject({NameObject("/Kids"): ArrayObject([leaf_b, leaf_c])})
    )
    embedded = writer._add_object(
        DictionaryObject({NameObject("/Kids"): ArrayObject([leaf_a, nested])})
    )
    names = writer._add_object(
        DictionaryObject({NameObject("/EmbeddedFiles"): embedded})
    )
    root[NameObject("/Names")] = names
    return 3


def test_inventory_lists_all_sources(pdf_with_metadata):
    reader = PdfReader(str(pdf_with_metadata))
    inv = sanitize_service.inventory(reader)

    # /Info: the standard keys plus the injected custom one.
    assert "/Title" in inv.info_keys
    assert "/Author" in inv.info_keys
    assert "/CustomCorp" in inv.info_keys

    # XMP /Metadata at the catalog root and on page 1.
    assert inv.xmp_catalog is True
    assert 1 in inv.xmp_pages

    # Trailer /ID.
    assert inv.trailer_id is True

    # /PieceInfo, catalog and per-page.
    assert inv.piece_info_catalog is True
    assert 1 in inv.piece_info_pages

    # Annotation carrying identifying keys.
    assert inv.annotations >= 1

    # Embedded files, JavaScript, outlines, named destinations.
    assert inv.embedded_files >= 1
    assert inv.javascript is True
    assert inv.outlines is True
    assert inv.named_dests >= 1

    # Every source is reflected in the summary/total.
    assert inv.total() > 0
    summary = inv.summary()
    assert summary
    assert sum(summary.values()) == inv.total()


def test_sanitize_removes_all_sources(pdf_with_metadata):
    reader = PdfReader(str(pdf_with_metadata))
    writer = PdfWriter(clone_from=reader)
    sanitize_service.sanitize(writer)

    inv = sanitize_service.inventory(writer)
    assert inv.total() == 0
    assert inv.info_keys == []
    assert inv.xmp_catalog is False
    assert inv.xmp_pages == []
    assert inv.trailer_id is False
    assert inv.piece_info_catalog is False
    assert inv.piece_info_pages == []
    assert inv.annotations == 0
    assert inv.embedded_files == 0
    assert inv.javascript is False
    assert inv.outlines is False
    assert inv.named_dests == 0


def test_inventory_counts_nested_kids_name_tree(three_page_pdf):
    """Name trees that use intermediate /Kids nodes (no top-level /Names leaf)
    must still be counted, so the proof-of-scrub doesn't read 0 -> 0."""
    reader = PdfReader(str(three_page_pdf))
    writer = PdfWriter(clone_from=reader)
    expected = _embedded_files_via_kids(writer)

    inv = sanitize_service.inventory(writer)
    assert inv.embedded_files == expected

    # And sanitize still removes the whole tree.
    sanitize_service.sanitize(writer)
    assert sanitize_service.inventory(writer).embedded_files == 0


def test_sanitize_preserves_text_layer(pdf_with_metadata, tmp_path):
    reader = PdfReader(str(pdf_with_metadata))
    writer = PdfWriter(clone_from=reader)
    page_count = len(writer.pages)
    sanitize_service.sanitize(writer)

    dest = tmp_path / "sanitized.pdf"
    with dest.open("wb") as f:
        writer.write(f)

    out = PdfReader(str(dest))
    assert len(out.pages) == page_count
    assert "Page 1" in out.pages[0].extract_text()
