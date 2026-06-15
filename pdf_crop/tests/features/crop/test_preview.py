from PIL import Image

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


# --- rendered page-image preview (UTILS-5) -----------------------------------


async def _settle_renders(app, pilot):
    """Pump the loop until no render workers are pending/running.

    Can't use `app.workers.wait_for_complete()`: an exclusive worker cancels the
    prior render mid-flight, and that helper re-raises `WorkerCancelled`.
    """
    from textual.worker import WorkerState

    for _ in range(50):
        active = [
            w
            for w in app.workers
            if w.group == "preview-render"
            and w.state in (WorkerState.PENDING, WorkerState.RUNNING)
        ]
        if not active:
            return
        await pilot.pause()


async def test_navigation_renders_current_page(three_page_pdf, monkeypatch):
    # Changing `current` (via goto/next/prev) renders the *current* page; the
    # fitz->PIL boundary is mocked so the test stays headless and fast.
    from pdf_crop.app import PdfCropApp

    rendered: list[int] = []

    def fake_render(self, page_number):
        rendered.append(page_number)
        return Image.new("RGB", (4, 4), "white")

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        # Mount renders page 1.
        assert 1 in rendered
        rendered.clear()
        preview.next()  # -> page 2
        await _settle_renders(app, pilot)
        assert rendered[-1] == 2


async def test_render_failure_shows_inline_message(three_page_pdf, monkeypatch):
    # A render failure surfaces an inline "Preview unavailable" message and never
    # lets an exception escape and crash the app.
    from pdf_crop.app import PdfCropApp

    def boom(self, page_number):
        raise ValueError("render kaboom")

    monkeypatch.setattr(PagePreview, "_render_page_image", boom)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        from textual.widgets import Static

        message = str(preview.query_one("#preview_message", Static).content)
        assert "Preview unavailable" in message
        assert "render kaboom" in message
        assert app.is_running is True


async def test_latest_page_wins_under_fast_navigation(three_page_pdf, monkeypatch):
    # With an exclusive worker, rapid navigation collapses to the final page: the
    # last `current` is the one that ends up rendered into the widget.
    from pdf_crop.app import PdfCropApp

    last_rendered: list[int] = []

    def fake_render(self, page_number):
        img = Image.new("RGB", (4, 4), "white")
        last_rendered.append(page_number)
        return img

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        preview.goto(2)
        preview.goto(3)
        await _settle_renders(app, pilot)
        # Whatever interleaving the exclusive worker took, the latest current (3)
        # is the page that was last rendered.
        assert last_rendered[-1] == 3
        assert preview.current == 3
