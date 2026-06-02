import unicodedata

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


def test_detects_curp():
    text = "CURP MAHJ800101HDFRRN09 registrada"
    matches = detect(text, categories={"curp"}, names=[])
    assert [m.text for m in matches] == ["MAHJ800101HDFRRN09"]


def test_detects_rfc_with_homoclave():
    text = "RFC MAHJ800101AB1 hoy"
    matches = detect(text, categories={"rfc"}, names=[])
    assert [m.text for m in matches] == ["MAHJ800101AB1"]


def test_rfc_and_curp_independent_categories():
    text = "MAHJ800101HDFRRN09"  # a valid CURP shape
    assert detect(text, categories={"rfc"}, names=[]) == []


def test_detects_name_case_and_accent_insensitive():
    text = "Pago a JOSE PEREZ por servicios"
    matches = detect(text, categories={"name"}, names=["José Pérez"])
    assert len(matches) == 1
    assert matches[0].category == "name"
    assert matches[0].text == "JOSE PEREZ"


def test_ignores_blank_name_entries():
    text = "Hola mundo"
    assert detect(text, categories={"name"}, names=["", "   "]) == []


def test_name_not_matched_when_category_disabled():
    assert detect("José Pérez", categories=set(), names=["José Pérez"]) == []


def test_overlapping_matches_are_merged():
    text = "002010077777777771"
    matches = detect(text, categories={"clabe", "card"}, names=[])
    spans = sorted((m.start, m.end) for m in matches)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2


def test_matches_returned_sorted_by_start():
    text = "JOSE 002010077777777771"
    matches = detect(text, categories={"clabe", "name"}, names=["Jose"])
    starts = [m.start for m in matches]
    assert starts == sorted(starts)


# Fix C1: NFD-normalised input text must produce correct offsets
def test_detects_name_in_nfd_normalized_text():
    text = unicodedata.normalize("NFD", "Pago a José Pérez hoy")
    matches = detect(text, categories={"name"}, names=["José Pérez"])
    assert len(matches) == 1
    assert text[matches[0].start:matches[0].end] == unicodedata.normalize("NFD", "José Pérez")


# Fix I1: CLABE must not match inside alphanumeric tokens
def test_clabe_not_matched_inside_alphanumeric_token():
    assert detect("ABC002010077777777771", categories={"clabe"}, names=[]) == []
    assert detect("002010077777777771X", categories={"clabe"}, names=[]) == []


def test_clabe_not_matched_inside_longer_digit_run():
    assert detect("00201007777777777100", categories={"clabe"}, names=[]) == []


# Fix I2: name matching must respect word boundaries
def test_name_does_not_match_partial_word():
    assert detect("Banana republic", categories={"name"}, names=["Ana"]) == []


def test_name_matches_whole_word_only():
    matches = detect("Ana y Banana", categories={"name"}, names=["Ana"])
    assert len(matches) == 1
    assert matches[0].start == 0


# Fix m2: card with dash separators
def test_detects_card_all_dash_groups():
    matches = detect("4539-5787-6362-1486", categories={"card"}, names=[])
    assert len(matches) == 1
    assert matches[0].text == "4539-5787-6362-1486"
