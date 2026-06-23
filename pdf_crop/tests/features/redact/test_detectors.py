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


# --- UTILS-19: space-separated CLABE ---------------------------------------


def test_detects_space_separated_clabe_and_spans_the_groups():
    # Statements print the CLABE in groups; the 18 digits are split by single
    # spaces. The match span must cover the whole grouped run so the spaces are
    # redacted too (otherwise stray digit-groups leak through).
    text = "CLABE 012 180 01234567890 1 vigente"
    matches = detect(text, categories={"clabe"}, names=[])
    assert len(matches) == 1
    m = matches[0]
    assert m.category == "clabe"
    assert m.text == "012 180 01234567890 1"
    assert text[m.start:m.end] == "012 180 01234567890 1"
    # Normalised it is exactly 18 digits.
    assert len("".join(c for c in m.text if c.isdigit())) == 18


def test_contiguous_clabe_still_matches():
    text = "Cuenta CLABE 002010077777777771 vigente"
    matches = detect(text, categories={"clabe"}, names=[])
    assert [m.text for m in matches] == ["002010077777777771"]


def test_spaced_run_of_17_or_19_digits_not_clabe():
    # 17 digits across groups: 3+3+10+1 = 17
    assert detect("012 180 0123456789 0", categories={"clabe"}, names=[]) == []
    # 19 digits across groups: 3+3+12+1 = 19
    assert detect("012 180 012345678901 2", categories={"clabe"}, names=[]) == []


def test_spaced_clabe_not_matched_inside_alphanumeric_token():
    # Boundaries must hold even with the spaced form.
    assert detect("AB012 180 01234567890 1", categories={"clabe"}, names=[]) == []
    assert detect("012 180 01234567890 1X", categories={"clabe"}, names=[]) == []


def test_spaced_18_digits_without_clabe_cue_not_matched():
    # A space-separated run is only trusted after a "CLABE" cue; without it, an
    # 18-digit spaced run must NOT be redacted.
    assert detect("012 180 01234567890 1 vigente", categories={"clabe"}, names=[]) == []


def test_unrelated_digit_groups_totaling_18_not_clabe():
    # Statement number sequences (refs, folios, phone+amount, dates) often place
    # several digit groups adjacent; totalling 18 must not become a CLABE.
    for text in (
        "Ref 123456789 987654321 end",    # two 9-digit refs = 18
        "Folio 123456 789012 345678 ok",  # three 6-digit groups = 18
        "20260615 1234567890",            # date (8) + number (10) = 18
    ):
        assert detect(text, categories={"clabe"}, names=[]) == [], text


# --- UTILS-19: label-anchored bank account numbers --------------------------


def test_detects_account_after_cuenta_label():
    text = "Cuenta: 0123456789 al corte"
    matches = detect(text, categories={"account"}, names=[])
    assert len(matches) == 1
    m = matches[0]
    assert m.category == "account"
    assert m.text == "0123456789"


def test_detects_account_after_no_de_cuenta_label():
    # BBVA-style 10-digit account behind "No. de cuenta".
    text = "No. de cuenta 0012345678 saldo"
    matches = detect(text, categories={"account"}, names=[])
    assert [m.category for m in matches] == ["account"]
    assert [m.text for m in matches] == ["0012345678"]


def test_detects_11_digit_santander_account_after_cta():
    # Santander accounts run ~11 digits.
    text = "Cta 01234567890 MXN"
    matches = detect(text, categories={"account"}, names=[])
    assert [m.text for m in matches] == ["01234567890"]


def test_detects_12_digit_banregio_account_accent_insensitive():
    # Banregio (and its digital arm Hey Banco) accounts run up to 12 digits;
    # the cue is accent/case insensitive ("Núm. de cuenta").
    text = "NÚM. DE CUENTA 012345678901 activa"
    matches = detect(text, categories={"account"}, names=[])
    assert [m.text for m in matches] == ["012345678901"]


def test_detects_spaced_account_run_and_spans_the_spaces():
    text = "Cuenta: 0123 456789 saldo"
    matches = detect(text, categories={"account"}, names=[])
    assert len(matches) == 1
    assert matches[0].text == "0123 456789"


def test_detects_account_after_cta_with_period():
    # "Cta." with a trailing period is a very common abbreviation.
    matches = detect("Cta. 0123456789 saldo", categories={"account"}, names=[])
    assert [m.text for m in matches] == ["0123456789"]


def test_account_cue_cta_not_matched_inside_other_words():
    # The short cue "cta" must not match as the tail of common Spanish words.
    assert detect("linea recta 0123456789", categories={"account"}, names=[]) == []
    assert detect("venta directa 0123456789", categories={"account"}, names=[]) == []


# --- UTILS-19: account NEGATIVES (precision over recall) --------------------


def test_bare_account_length_number_without_label_not_matched():
    # A bare 10- or 11-digit run with no account cue must NOT be redacted.
    assert detect("0123456789 referencia", categories={"account"}, names=[]) == []
    assert detect("01234567890", categories={"account"}, names=[]) == []


def test_amount_or_date_without_label_not_matched_as_account():
    # Amounts and dates near no cue must not trip the account detector.
    assert detect("Importe 12,345.67 MXN el 2026-06-15", categories={"account"}, names=[]) == []
    assert detect("Fecha 15/06/2026 corte", categories={"account"}, names=[]) == []


def test_cuenta_clabe_label_yields_clabe_not_account():
    # "Cuenta CLABE" is the 18-digit CLABE — detector #1, not the account one.
    text = "Cuenta CLABE 002010077777777771 vigente"
    matches = detect(text, categories={"clabe", "account"}, names=[])
    assert len(matches) == 1
    assert matches[0].category == "clabe"
    assert matches[0].text == "002010077777777771"


def test_16_digit_card_after_cuenta_not_matched_as_account():
    # A 16-digit card behind a "Cuenta" cue is too long for an account run.
    text = "Cuenta 4539578763621486"
    matches = detect(text, categories={"account"}, names=[])
    assert [m.category for m in matches] == []


def test_18_digit_clabe_after_cuenta_not_matched_as_account():
    text = "Cuenta 002010077777777771"
    matches = detect(text, categories={"account"}, names=[])
    assert [m.category for m in matches] == []


def test_account_not_returned_when_category_disabled():
    assert detect("Cuenta: 0123456789", categories=set(), names=[]) == []


def test_account_and_clabe_do_not_double_match_same_span():
    # Even if both categories are on, a single 18-digit CLABE behind "Cuenta CLABE"
    # is one match, not an account+clabe overlap.
    text = "Cuenta CLABE 012180012345678901 fin"
    matches = detect(text, categories={"clabe", "account"}, names=[])
    spans = sorted((m.start, m.end) for m in matches)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2


# --- UTILS-20: Mexican address NEGATIVES (precision over recall) ------------


def test_bare_postal_code_without_cp_cue_not_matched():
    # A bare 5-digit number with NO "C.P."/"CP" cue must NOT be matched — it
    # could be anything (a folio, a year+digit, etc.).
    assert detect("64000 referencia", categories={"address"}, names=[]) == []
    assert detect("Total 64000 pesos", categories={"address"}, names=[]) == []


def test_generic_no_not_matched_as_address():
    # "No. de operación" / "No. de cuenta" use the generic "No." which is NOT an
    # address cue — a bare "No." must never trigger a street-line redaction.
    assert detect("No. de operación 12345", categories={"address"}, names=[]) == []
    assert detect("No. de cuenta 0123456789", categories={"address"}, names=[]) == []


def test_ordinary_sentence_with_hash_or_no_not_matched():
    # The generic "#" and "No." tokens in an ordinary sentence are too weak to be
    # standalone address triggers.
    assert detect("Tu pedido # 7 está listo.", categories={"address"}, names=[]) == []
    assert detect("Apartado No. 5 del contrato.", categories={"address"}, names=[]) == []


def test_street_cue_as_common_noun_in_prose_not_matched():
    # The strong cues (calle/avenida/col/av/...) are also ordinary Spanish nouns.
    # Without a number later on the line a match must NOT fire, even though the cue
    # word is present — otherwise plain prose gets wiped to end-of-line.
    for text in (
        "Caminé por la calle principal ayer por la tarde.",
        "La avenida estaba cerrada por obras toda la mañana.",
        "Disolvimos la col. de agua en el matraz.",
        "El equipo av jugó bien en el segundo tiempo.",
        "Calle abajo encontrará nuestras oficinas.",
        "Vivimos en la colonia de inversionistas.",
    ):
        assert detect(text, categories={"address"}, names=[]) == [], text


def test_address_not_returned_when_category_disabled():
    text = "C.P. 64000 Calle Reforma 123"
    assert detect(text, categories=set(), names=[]) == []


def test_only_street_and_cp_lines_matched_in_block_surrounding_lines_untouched():
    # A multi-line block: only the street/CP-cued lines are redacted; the
    # surrounding ordinary lines stay untouched (no whole-block redaction).
    text = "\n".join([
        "Estimado cliente,",
        "Calle Reforma 123, Col. Centro",
        "Ciudad de México",
        "Gracias por su preferencia.",
    ])
    matches = detect(text, categories={"address"}, names=[])
    redacted = {text[m.start:m.end] for m in matches}
    assert "Calle Reforma 123, Col. Centro" in redacted
    # The non-address lines are never part of any match span.
    for m in matches:
        assert "Estimado cliente," not in text[m.start:m.end]
        assert "Ciudad de México" not in text[m.start:m.end]
        assert "Gracias por su preferencia." not in text[m.start:m.end]


# --- UTILS-20: Mexican address POSITIVES ------------------------------------


def test_detects_postal_code_with_cp_cue():
    text = "Domicilio C.P. 64000 Monterrey"
    matches = detect(text, categories={"address"}, names=[])
    assert len(matches) == 1
    m = matches[0]
    assert m.category == "address"
    assert m.text == "C.P. 64000"
    assert text[m.start:m.end] == "C.P. 64000"


def test_detects_postal_code_with_cp_no_dots():
    # No strong street cue on the line — exercises the bare "CP NNNNN" form in
    # isolation (the span covers the cue + code, not the surrounding text).
    text = "Centro, CP 06000 alcaldía Cuauhtémoc"
    matches = detect(text, categories={"address"}, names=[])
    assert [m.category for m in matches] == ["address"]
    assert matches[0].text == "CP 06000"


def test_detects_street_line_bounded_to_its_line():
    # The street cue redacts to end-of-line; a following line is NOT swallowed.
    text = "Calle Reforma 123, Col. Centro\nCiudad de México"
    matches = detect(text, categories={"address"}, names=[])
    assert len(matches) == 1
    assert matches[0].text == "Calle Reforma 123, Col. Centro"
    assert "Ciudad de México" not in matches[0].text


def test_detects_avenida_street_line():
    text = "Av. Insurgentes Sur 1234"
    matches = detect(text, categories={"address"}, names=[])
    assert [m.text for m in matches] == ["Av. Insurgentes Sur 1234"]


def test_detects_street_cues_case_and_accent_insensitive():
    # Strong cues are recognised regardless of case/accents.
    text = "AVENIDA Juárez 50\nCALZADA de Tlalpan 900"
    matches = detect(text, categories={"address"}, names=[])
    redacted = {m.text for m in matches}
    assert "AVENIDA Juárez 50" in redacted
    assert "CALZADA de Tlalpan 900" in redacted


def test_address_cue_not_matched_inside_other_words():
    # The strong cues must not match as the tail/head of unrelated words
    # ("avenida" inside "desavenida", "calle" inside "encalle").
    assert detect("una desavenida lamentable", categories={"address"}, names=[]) == []


def test_street_line_containing_cp_merges_to_single_match():
    # A street line that also carries a C.P. is a single redacted line, not an
    # overlapping street+CP pair.
    text = "Calle Hidalgo 45, C.P. 64000"
    matches = detect(text, categories={"address"}, names=[])
    spans = sorted((m.start, m.end) for m in matches)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2
    # The whole line is covered.
    assert any(text[m.start:m.end] == "Calle Hidalgo 45, C.P. 64000" for m in matches)
