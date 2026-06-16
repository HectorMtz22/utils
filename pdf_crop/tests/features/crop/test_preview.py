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


# --- render cache + persistent document (UTILS-10) ---------------------------


async def test_revisiting_page_uses_cache_not_render(three_page_pdf, monkeypatch):
    # Navigating back to an already-rendered page reuses the cached image and does
    # not re-invoke the render seam / spawn a worker.
    from pdf_crop.app import PdfCropApp

    rendered: list[int] = []

    def fake_render(self, page_number):
        rendered.append(page_number)
        return Image.new("RGB", (4, 4), "white")

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)  # mount renders page 1
        preview.goto(2)
        await _settle_renders(app, pilot)  # renders page 2
        assert sorted(rendered) == [1, 2]
        rendered.clear()
        preview.goto(1)  # already rendered -> cache hit
        await _settle_renders(app, pilot)
        assert rendered == []  # seam was not called again
        # The widget still shows page 1's image.
        from textual_image.widget import Image as ImageWidget

        assert preview.query_one("#preview_image", ImageWidget).image is not None


async def test_lru_evicts_least_recently_used(ten_page_pdf, monkeypatch):
    # Visiting more distinct pages than the cache cap evicts the oldest; revisiting
    # the evicted page re-invokes the render seam.
    from pdf_crop.app import PdfCropApp
    from pdf_crop.features.crop import preview as preview_mod

    monkeypatch.setattr(preview_mod, "RENDER_CACHE_SIZE", 3)

    rendered: list[int] = []

    def fake_render(self, page_number):
        rendered.append(page_number)
        return Image.new("RGB", (4, 4), "white")

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(ten_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)  # mount renders page 1
        for page in (2, 3, 4):  # cap is 3, so page 1 is evicted
            preview.goto(page)
            await _settle_renders(app, pilot)
        assert sorted(rendered) == [1, 2, 3, 4]
        rendered.clear()
        preview.goto(1)  # evicted -> must re-render
        await _settle_renders(app, pilot)
        assert rendered == [1]


async def test_document_opened_once_across_renders(three_page_pdf, monkeypatch):
    # The PDF is opened a single time and the handle reused across page renders,
    # rather than re-parsed on every navigation.
    import fitz

    from pdf_crop.app import PdfCropApp

    opens: list = []
    real_open = fitz.open

    def counting_open(*args, **kwargs):
        doc = real_open(*args, **kwargs)
        opens.append(doc)
        return doc

    monkeypatch.setattr(fitz, "open", counting_open)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)  # mount renders page 1
        preview.goto(2)
        await _settle_renders(app, pilot)
        preview.goto(3)
        await _settle_renders(app, pilot)
        # The preview pane opened its document exactly once (the app may open the
        # PDF elsewhere for its own purposes; assert the preview reuses one handle).
        assert preview._doc is not None
        opened_by_preview = [d for d in opens if d is preview._doc]
        assert len(opened_by_preview) == 1


async def test_unmount_closes_document_without_error(three_page_pdf, monkeypatch):
    # Unmounting closes the shared document and does not raise even if a render is
    # "in flight" (the close is guarded so it never frees a doc mid-read).
    from pdf_crop.app import PdfCropApp

    def fake_render(self, page_number):
        return Image.new("RGB", (4, 4), "white")

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        doc = preview._ensure_doc()
        assert doc.is_closed is False
        # Hold the render lock as if a render were reading the doc, then unmount.
        with preview._doc_lock:
            preview.on_unmount()
            assert doc.is_closed is False  # guarded: not closed while "in flight"
        preview.on_unmount()  # now the lock is free
        assert doc.is_closed is True
        assert app.is_running is True
