from pypdf.generic import (
    ByteStringObject,
    ContentStream,
    TextStringObject,
)

# Operators that show glyphs. The TJ array is handled separately (it interleaves
# strings with kerning numbers).
_SHOW_OPS = {b"Tj", b"'", b'"'}

# Default font size when a BT block shows text before any Tf operator. Statements
# always set a font, but a hand-built stream might not.
_DEFAULT_FONT_SIZE = 12.0

# Average glyph advance in ems. Tabular digits — the values users redact — sit at
# roughly half an em, so tracking the pen as `n * GLYPH_W * font_size * scale`
# keeps continuation/gap decisions accurate for numbers without needing real
# font-width tables.
GLYPH_W = 0.5

# Separator thresholds, in ems of the current font. A baseline shift beyond
# _NEWLINE_DY_EM is a new row; a same-line forward jump beyond _SPACE_DX_EM is a
# new column / word gap. Used by both gap_sep() and the TJ-kerning check, which
# must stay in sync.
_NEWLINE_DY_EM = 0.3
_SPACE_DX_EM = 0.5


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
    """Reconstruct page text, inserting separators from the text-pen geometry.

    Tables position each cell with a `Tm` (text-matrix) and emit no break op
    between cells, so a separator can't come from the operator name alone — it
    has to come from the GAP between where the previous glyph ended and where the
    next run starts. We track a text line origin, the pen, the horizontal scale,
    leading, and font size across each BT…ET block:

      * baseline y changes  -> newline
      * same line, the next run starts well past the pen (new column / word) -> space
      * the next run starts at/near the pen -> continuation, no separator

    This subsumes Tm jumps, large TJ kerning, and horizontal Td uniformly. Each
    inserted separator is a SYNTHETIC charmap entry (-1, -1, -1) — exactly like
    the old newline handling — so delete_spans (which skips op_index == -1) stays
    surgical and len(charmap) == len(text) holds.
    """
    text = []
    charmap = []

    # Text-space state, reset at each BT. lx/ly is the current line origin;
    # px/py is the pen; scale is Tm's horizontal scale `a`; leading is TL.
    lx = ly = px = py = 0.0
    scale = 1.0
    leading = 0.0
    font_size = _DEFAULT_FONT_SIZE
    has_pos = False  # have we adopted any position in this block yet?

    def sep(kind):
        # Append a synthetic separator unless one would lead the text or double up.
        if text and text[-1] not in ("\n", " "):
            text.append(kind)
            charmap.append((-1, -1, -1))

    def gap_sep(new_x, new_y):
        # Decide a separator vs the current pen for an absolute move to new_x/new_y.
        if not (has_pos and text):
            return
        if abs(new_y - py) > _NEWLINE_DY_EM * font_size:
            sep("\n")
        elif (new_x - px) > _SPACE_DX_EM * font_size:
            sep(" ")
        # new_x <= px: the next run starts at or behind the pen -> treated as
        # continuation (no separator). This assumes left-to-right column order;
        # a right-to-left layout, or a header re-drawn at a smaller x on the same
        # baseline, will fuse the two runs back together. Known limitation, pinned
        # by test_leftward_same_line_cell_is_a_known_fusion_limitation.

    for op_index, (operands, operator) in enumerate(cs.operations):
        if operator == b"BT":
            # BT resets the text & text-line matrices to identity, so a relative
            # Td/TD/T* in this block is measured from origin (0, 0). The absolute
            # pen (px, py) and has_pos are deliberately KEPT across BT…ET: a table
            # commonly draws each cell in its own BT…ET block positioned by an
            # absolute Tm, so the next block's Tm must still be able to compare
            # against where the previous block's pen ended (else cells refuse).
            lx = ly = 0.0
            scale = 1.0
        elif operator == b"Tf":
            font_size = float(operands[-1])
        elif operator == b"TL":
            leading = float(operands[-1])
        elif operator == b"Tm":
            a, _b, _c, _d, e, f = (float(x) for x in operands[:6])
            gap_sep(e, f)
            lx = px = e
            ly = py = f
            scale = a
            has_pos = True
        elif operator in (b"Td", b"TD"):
            tx, ty = float(operands[0]), float(operands[1])
            if operator == b"TD":
                leading = -ty
            newx, newy = lx + tx, ly + ty
            gap_sep(newx, newy)
            lx = px = newx
            ly = py = newy
            has_pos = True
        elif operator == b"T*":
            # Equivalent to `Td 0 -TL` -> moves down a line: a newline.
            newx, newy = lx, ly - leading
            gap_sep(newx, newy)
            lx = px = newx
            ly = py = newy
            has_pos = True

        if operator in _SHOW_OPS:
            # `'` and `"` also advance to the next line first (like T*). The
            # text-state handling for `'`/`"` is via their being in _SHOW_OPS plus
            # T*-style movement below; reportlab/statements use Tj + explicit T*,
            # so this path mainly serves hand-built or quote-operator streams.
            if operator in (b"'", b'"'):
                newx, newy = lx, ly - leading
                gap_sep(newx, newy)
                lx = px = newx
                ly = py = newy
                has_pos = True
            s = str(operands[-1])
            _emit(text, charmap, s, op_index, -1)
            px += len(s) * GLYPH_W * font_size * scale
            has_pos = True
        elif operator == b"TJ":
            for el_index, el in enumerate(operands[0]):
                if isinstance(el, (TextStringObject, ByteStringObject)):
                    s = str(el)
                    _emit(text, charmap, s, op_index, el_index)
                    px += len(s) * GLYPH_W * font_size * scale
                    has_pos = True
                else:
                    # Numeric kerning element: a positive `gap` moves the pen
                    # right (TJ numbers subtract thousandths of an em). A big
                    # gap is a real word/column break -> space.
                    gap = -float(el) / 1000.0 * font_size * scale
                    px += gap
                    if gap > _SPACE_DX_EM * font_size and text:
                        sep(" ")

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
                continue  # synthetic separator
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
