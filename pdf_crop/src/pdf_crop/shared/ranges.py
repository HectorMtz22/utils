from pdf_crop.shared.errors import InvalidRangeSyntax, PageOutOfRange


def parse(expr: str, total_pages: int) -> list[int]:
    """Parse a page expression like '1-5,8,11-13' into a sorted, deduped page list.

    Pages are 1-indexed. Raises InvalidRangeSyntax for malformed input,
    PageOutOfRange when any page is < 1 or > total_pages.
    """
    if not expr or not expr.strip():
        raise InvalidRangeSyntax("range expression is empty")

    pages: set[int] = set()
    for raw_token in expr.split(","):
        token = raw_token.strip()
        if not token:
            raise InvalidRangeSyntax(f"empty segment in '{expr}'")

        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2:
                raise InvalidRangeSyntax(f"malformed range '{token}'")
            left, right = parts[0].strip(), parts[1].strip()
            if not left or not right:
                raise InvalidRangeSyntax(f"malformed range '{token}'")
            try:
                start = int(left)
                end = int(right)
            except ValueError:
                raise InvalidRangeSyntax(f"non-numeric value in '{token}'") from None
            if start < 1 or end < 1:
                raise PageOutOfRange(f"pages must be >= 1, got '{token}'")
            if start > end:
                raise InvalidRangeSyntax(f"descending range '{token}'")
            if end > total_pages:
                raise PageOutOfRange(
                    f"page {end} exceeds document length {total_pages}"
                )
            pages.update(range(start, end + 1))
        else:
            try:
                page = int(token)
            except ValueError:
                raise InvalidRangeSyntax(f"non-numeric value '{token}'") from None
            if page < 1:
                raise PageOutOfRange(f"pages must be >= 1, got {page}")
            if page > total_pages:
                raise PageOutOfRange(
                    f"page {page} exceeds document length {total_pages}"
                )
            pages.add(page)

    return sorted(pages)
