from pdf_crop.features.redact.detectors import Match, detect


def test_detects_clabe_18_digits():
    text = "Cuenta CLABE 002010077777777771 vigente"
    matches = detect(text, categories={"clabe"}, names=[])
    assert len(matches) == 1
    m = matches[0]
    assert m.category == "clabe"
    assert m.text == "002010077777777771"
    assert text[m.start:m.end] == "002010077777777771"


def test_ignores_17_or_19_digit_runs():
    assert detect("12345678901234567", categories={"clabe"}, names=[]) == []
    assert detect("1234567890123456789", categories={"clabe"}, names=[]) == []


def test_clabe_not_returned_when_category_disabled():
    text = "002010077777777771"
    assert detect(text, categories=set(), names=[]) == []


def test_detects_luhn_valid_card():
    text = "Tarjeta 4539578763621486 fin"
    matches = detect(text, categories={"card"}, names=[])
    assert [m.text for m in matches] == ["4539578763621486"]


def test_rejects_luhn_invalid_16_digits():
    text = "4539578763621487"
    assert detect(text, categories={"card"}, names=[]) == []


def test_detects_card_in_4digit_groups():
    text = "4539 5787 6362 1486"
    matches = detect(text, categories={"card"}, names=[])
    assert len(matches) == 1
    assert matches[0].text == "4539 5787 6362 1486"
