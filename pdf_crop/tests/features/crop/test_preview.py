from pdf_crop.features.crop.preview import PagePreview


def test_starts_on_first_page():
    preview = PagePreview(total=5)
    assert preview.current == 1
    assert preview.total == 5


def test_next_advances_one_page():
    preview = PagePreview(total=5)
    preview.next()
    assert preview.current == 2


def test_next_clamps_at_total():
    preview = PagePreview(total=3)
    preview.goto(3)
    preview.next()
    assert preview.current == 3


def test_prev_goes_back_one_page():
    preview = PagePreview(total=5)
    preview.goto(3)
    preview.prev()
    assert preview.current == 2


def test_prev_clamps_at_one():
    preview = PagePreview(total=5)
    preview.prev()
    assert preview.current == 1


def test_goto_clamps_below_one():
    preview = PagePreview(total=5)
    preview.goto(0)
    assert preview.current == 1


def test_goto_clamps_above_total():
    preview = PagePreview(total=5)
    preview.goto(99)
    assert preview.current == 5


def test_included_true_for_page_in_set():
    preview = PagePreview(total=5)
    preview.goto(3)
    assert preview.included({1, 2, 3}) is True


def test_included_false_for_page_not_in_set():
    preview = PagePreview(total=5)
    preview.goto(4)
    assert preview.included({1, 2, 3}) is False
