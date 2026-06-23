from pypdf.generic import (
    ByteStringObject,
    ContentStream,
    TextStringObject,
)

# Operators that move to a new line/position — insert a newline between their
# output so a number at the end of one line can't fuse with the next line's.
_BREAK_OPS = {b"Td", b"TD", b"T*", b"'", b'"'}
_SHOW_OPS = {b"Tj", b"'", b'"'}


def _content_stream(page):
    return ContentStream(page.get_contents(), page.pdf)


def page_text(page):
    """Reconstruct visible text and a per-char map to its source operator.

    Returns (text, charmap) where charmap[i] = (op_index, element_index, offset).
    element_index is the position inside a TJ array, or -1 for a plain string.
    offset is the character index into str(element), not a byte offset.
    """
    return _walk(_content_stream(page))


def _walk(cs):
    text = []
    charmap = []
    for op_index, (operands, operator) in enumerate(cs.operations):
        if operator in _BREAK_OPS and text and text[-1] != "\n":
            text.append("\n")
            charmap.append((-1, -1, -1))  # synthetic, never deleted
        if operator in _SHOW_OPS:
            _emit(text, charmap, str(operands[-1]), op_index, -1)
        elif operator == b"TJ":
            for el_index, el in enumerate(operands[0]):
                if isinstance(el, (TextStringObject, ByteStringObject)):
                    _emit(text, charmap, str(el), op_index, el_index)
    return "".join(text), charmap


def _emit(text, charmap, s, op_index, el_index):
    for offset, ch in enumerate(s):
        text.append(ch)
        charmap.append((op_index, el_index, offset))


def delete_spans(page, spans):
    """Delete the characters in each (start, end) char-span from `page`.

    Recomputes the same walk used by page_text so offsets line up, then rebuilds
    each affected text operand without the removed characters.
    """
    cs = _content_stream(page)
    _, charmap = _walk(cs)

    drop = {}  # (op_index, el_index) -> set of offsets to remove
    for start, end in spans:
        for i in range(start, end):
            op_index, el_index, offset = charmap[i]
            if op_index == -1:
                continue  # synthetic newline
            drop.setdefault((op_index, el_index), set()).add(offset)

    for (op_index, el_index), offsets in drop.items():
        operands, operator = cs.operations[op_index]
        if el_index == -1:
            operands[-1] = TextStringObject(_strip(str(operands[-1]), offsets))
        else:
            operands[0][el_index] = TextStringObject(_strip(str(operands[0][el_index]), offsets))
        cs.operations[op_index] = (operands, operator)

    # Replace via the page API so /Contents is written as a proper *indirect*
    # stream. A direct `page["/Contents"] = cs` assignment produces a malformed
    # page on anything with an image layer (e.g. a scanned/templated statement):
    # the page renders blank and MuPDF reports "syntax error in dict". The
    # reader-attached deprecation warning the old hack avoided doesn't fire here
    # — redaction runs on writer pages.
    page.replace_contents(cs)


def _strip(s, offsets):
    return "".join(ch for i, ch in enumerate(s) if i not in offsets)
