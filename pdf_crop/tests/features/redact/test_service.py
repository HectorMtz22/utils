from pdf_crop.shared.pdf_io import open_pdf
from pdf_crop.features.redact import service


def test_scan_counts_matches_per_category(text_pdf_factory):
    src = text_pdf_factory([
        "CLABE 002010077777777771 de JOSE PEREZ",
        "Otra pagina sin datos",
    ])
    reader = open_pdf(src)
    findings = service.scan(reader, [1, 2], categories={"clabe", "name"}, names=["Jose Perez"])
    assert findings.summary() == {"clabe": 1, "name": 1}
    assert set(findings.by_page) == {1}  # only page 1 (1-indexed) had matches


def test_scan_empty_when_no_text(three_page_pdf):
    reader = open_pdf(three_page_pdf)
    findings = service.scan(reader, [1, 2, 3], categories={"clabe", "card"}, names=[])
    assert findings.matches == []
    assert findings.summary() == {}
