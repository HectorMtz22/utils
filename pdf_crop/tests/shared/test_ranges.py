import pytest

from pdf_crop.shared.ranges import parse
from pdf_crop.shared.errors import InvalidRangeSyntax, PageOutOfRange


class TestParseHappyPath:
    def test_single_page(self):
        assert parse("3", total_pages=10) == [3]

    def test_single_range(self):
        assert parse("2-5", total_pages=10) == [2, 3, 4, 5]

    def test_multiple_singles(self):
        assert parse("1,3,7", total_pages=10) == [1, 3, 7]

    def test_mixed_singles_and_ranges(self):
        assert parse("1-3,5,8-9", total_pages=10) == [1, 2, 3, 5, 8, 9]

    def test_whitespace_tolerated(self):
        assert parse(" 1 - 3 , 5 , 8 - 9 ", total_pages=10) == [1, 2, 3, 5, 8, 9]

    def test_duplicates_collapsed(self):
        assert parse("1,1,2-3,3", total_pages=10) == [1, 2, 3]

    def test_overlapping_ranges_merged(self):
        assert parse("1-5,4-7", total_pages=10) == [1, 2, 3, 4, 5, 6, 7]

    def test_full_document(self):
        assert parse("1-10", total_pages=10) == list(range(1, 11))


class TestParseSyntaxErrors:
    @pytest.mark.parametrize("expr", ["", "   ", ",", "1,,2", "1-", "-3", "1-2-3", "abc", "1-x", "x-2"])
    def test_invalid_syntax(self, expr):
        with pytest.raises(InvalidRangeSyntax):
            parse(expr, total_pages=10)

    def test_descending_range(self):
        with pytest.raises(InvalidRangeSyntax):
            parse("5-2", total_pages=10)


class TestParseOutOfRange:
    def test_zero(self):
        with pytest.raises(PageOutOfRange):
            parse("0", total_pages=10)

    def test_negative(self):
        with pytest.raises(InvalidRangeSyntax):
            # "-3" is malformed (empty left side), so syntax error, not OOR
            parse("-3", total_pages=10)

    def test_single_above_total(self):
        with pytest.raises(PageOutOfRange):
            parse("11", total_pages=10)

    def test_range_end_above_total(self):
        with pytest.raises(PageOutOfRange):
            parse("8-12", total_pages=10)
