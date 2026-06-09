from pypdf import PdfReader, PdfWriter

from pdf_crop.features.sanitize import service as sanitize_service


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
