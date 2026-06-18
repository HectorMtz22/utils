import fitz
from PIL import Image

from pdf_crop.features.crop.preview import PagePreview
from pdf_crop.shared import imaging


# --- rasterizer aspect-ratio guard (UTILS-11) --------------------------------
#
# The preview distortion is a *display* bug (textual-image stretched the image
# when both CSS dimensions were pinned), not a rasterizer bug. This guard pins
# that down: `imaging.render_page` must produce a PIL image whose aspect ratio
# matches the source page's point-size ratio, so a future regression in the
# render pipeline can't be mistaken for the display fix.
def test_render_page_preserves_source_aspect_ratio():
    # A clearly portrait page (US Letter, 612x792 pt) so the assertion is
    # meaningful — a square page would pass even a ratio-mangling rasterizer.
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    source_ratio = page.rect.width / page.rect.height

    img = imaging.render_page(page, dpi=150)

    image_ratio = img.width / img.height
    # Rounding to whole pixels at 150 dpi introduces at most sub-pixel error;
    # a generous tolerance still catches any real squish/stretch.
    assert abs(image_ratio - source_ratio) < 0.01


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


# --- preview pane contains the image, doesn't stretch it (UTILS-11) ----------


async def test_preview_image_is_contained_not_stretched(three_page_pdf, monkeypatch):
    # The fix: `#preview_image` no longer pins both width and height, so
    # textual-image preserves the source aspect ratio and *contains* the image
    # within the pane instead of stretching it to fill the whole box.
    #
    # We feed a deliberately tall portrait image through the render seam, then
    # assert the displayed widget is narrower than the pane: a contained tall
    # image fills the pane's *height* and leaves horizontal slack, so its width
    # is strictly less than the pane's content width. textual-image's sizing is
    # deterministic headless (it derives a fixed cell geometry from
    # `get_cell_size`), so this is stable, not flaky. Under the buggy `1fr/1fr`
    # rule the image was forced to the pane's full width (and height), filling
    # the box and distorting the page — this assertion fails in that case.
    from pdf_crop.app import PdfCropApp
    from textual_image.widget import Image as ImageWidget

    # 1:4, much taller than wide, so a contained fit must leave horizontal slack.
    portrait = Image.new("RGB", (400, 1600), "white")

    def fake_render(self, page_number):
        return portrait

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()  # let layout resolve the image's content size

        image = preview.query_one("#preview_image", ImageWidget)
        pane_width = preview.content_size.width
        image_width = image.content_size.width
        # Sanity: the harness actually laid the widget out (non-zero), so the
        # assertion below is meaningful and not vacuously true on a 0x0 widget.
        assert pane_width > 0 and image.content_size.height > 0
        # Contained, not stretched: a tall page can't fill the pane width without
        # distortion, so the displayed image is strictly narrower than the pane.
        assert image_width < pane_width


# --- preview contains the page (fill height for tall, fit width for wide),
# --- and sits flush-right (UTILS-13) -----------------------------------------
#
# These guards assert the layout the CSS produces, not a pixel-accurate render:
# textual-image's headless cell geometry is deterministic under pytest (a
# non-tty gives a fixed `get_cell_size`), so the widget *regions* it lays out
# are stable and measurable. What a human still has to eyeball is whether the
# rendered glyphs *look* right in a real terminal — these tests only pin the
# geometry that drives that.
#
# The CSS is `#preview_image { width: auto; height: auto; }`: textual-image
# *contains* the page within the pane preserving aspect. A tall page is bound by
# the available height (fills the band, leaves horizontal slack); a wide page is
# bound by the width (fills the width, leaves vertical slack). Pinning a
# dimension (`height: 1fr`) is what distorts wide pages — see the wide-page
# guard below.


async def test_preview_image_tall_page_fills_band_without_overflow(
    three_page_pdf, monkeypatch
):
    # A tall portrait page is height-bound: contained within the pane it fills
    # the band between the (docked) nav row and (docked) message line, leaving
    # only horizontal slack. We assert the image and message both stay inside the
    # pane (no overflow) and the image spans the full nav-bottom..message-top
    # band, proving it fills the available height rather than collapsing to a
    # sliver. (Measured: a 1:4 page lays out exactly to the band — height ==
    # message.y - nav.bottom — under `height: auto`, same as it did under the old
    # `height: 1fr`, because for a tall page the height is the binding dimension
    # either way.)
    from pdf_crop.app import PdfCropApp
    from textual_image.widget import Image as ImageWidget

    # 1:4, much taller than wide, so the height is the binding dimension and a
    # contained fit fills the band exactly.
    portrait = Image.new("RGB", (400, 1600), "white")

    def fake_render(self, page_number):
        return portrait

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()

        image = preview.query_one("#preview_image", ImageWidget)
        nav = preview.query_one("#preview_nav")
        message = preview.query_one("#preview_message")
        pane = preview.content_region
        # Contained: neither the image nor the message overruns the pane bottom.
        assert image.region.bottom <= pane.bottom
        assert message.region.bottom <= pane.bottom
        # Fills the band: the image spans nav-bottom..message-top, so it's
        # filling the available height rather than collapsed to a sliver.
        assert image.region.height == message.region.y - nav.region.bottom
        assert image.region.height > 1


async def test_preview_image_wide_page_preserves_aspect(three_page_pdf, monkeypatch):
    # The regression guard for the #36 squish under a pinned height: a *wide*
    # (landscape) page must be contained preserving aspect, NOT stretched to the
    # full band. With `width: auto; height: auto` textual-image fits a wide page
    # to the pane *width* and lets the height shrink, leaving vertical slack — so
    # the image's region height is strictly less than the available band and its
    # width fills the pane's inner width. Under the buggy `height: 1fr` (with
    # `width: auto`) textual-image clamps the width to the pane but pins the
    # height to the whole 1fr band, distorting the page to the full box — this
    # assertion fails there (region height == band, not < band). Measured at
    # size=(120, 60): wide page region is 68w x 8h vs an available band of 48
    # under `auto` (passes), and 68w x 48h under `1fr` (fails).
    from pdf_crop.app import PdfCropApp
    from textual_image.widget import Image as ImageWidget

    # 4:1 landscape, ratio 4.0 — far wider than the pane's cell ratio, so a
    # contained fit must leave vertical slack.
    landscape = Image.new("RGB", (1600, 400), "white")

    def fake_render(self, page_number):
        return landscape

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()

        image = preview.query_one("#preview_image", ImageWidget)
        nav = preview.query_one("#preview_nav")
        message = preview.query_one("#preview_message")
        pane = preview.content_region
        band = message.region.y - nav.region.bottom
        # Sanity: the widget was actually laid out (non-zero), so the assertions
        # aren't vacuously true on a collapsed 0x0 widget.
        assert band > 1 and image.region.height > 0
        # Contained, not stretched: a wide page fits to width and leaves vertical
        # slack, so its region height is strictly less than the full band. Under
        # `height: 1fr` it was pinned to the whole band (height == band).
        assert image.region.height < band
        # Fit to width: the image fills the pane's inner content width.
        assert image.content_size.width == preview.content_size.width
        # Still inside the pane (no overflow past the bottom).
        assert image.region.bottom <= pane.bottom


# --- wrap pane: the frame hugs the Fit-sized page (UTILS-15) -----------------
#
# This supersedes the old UTILS-13 *flush-right* guard. Flush-right pushed a
# narrow image against the right edge of a fixed-width (60%) pane, relying on the
# pane being noticeably wider than the page. UTILS-15 makes the pane *hug* the
# page instead: `_pin_pane_to_fit` sizes #preview to the contained image plus its
# border+padding, so there is no longer meaningful horizontal slack to flush into
# — the image essentially fills the pane width (minus the scroll gutter). The
# premise of the flush-right test ("the image is much narrower than the pane, so
# push it right") no longer holds, so we assert the new contract: the page is
# contained with no overflow and the pane is sized to hug it, not left at a fixed
# fraction of the screen.


async def test_preview_pane_hugs_the_fit_page(three_page_pdf, monkeypatch):
    # Wrap pane: #preview is sized to the contained page (image + chrome), so its
    # width tracks the page rather than a fixed fraction of the screen, and
    # #controls (now width: 1fr) takes the rest. The image stays contained inside
    # the pane with no overflow, and the pane hugs it (only a thin gutter).
    from pdf_crop.app import PdfCropApp
    from textual_image.widget import Image as ImageWidget

    async def measure(image):
        """Mount with `image` as the page and return (pane_width, controls_width,
        pane_content_region, image_content_size)."""
        monkeypatch.setattr(PagePreview, "_render_page_image", lambda self, n: image)
        app = PdfCropApp(three_page_pdf)
        async with app.run_test(size=(120, 60)) as pilot:
            preview = app.screen.query_one(PagePreview)
            await _settle_renders(app, pilot)
            await pilot.pause()
            img = preview.query_one("#preview_image", ImageWidget)
            controls = app.screen.query_one("#controls")
            return (
                preview.region.width,
                controls.region.width,
                preview.content_region,
                img.content_size,
            )

    # Realistic A4 at 150 dpi (~1240x1754 px) in both orientations. Wide enough
    # that the nav row fits on one line, so the pane genuinely hugs the page (an
    # exaggerated 1:4 sliver would force the nav to wrap and loosen the hug).
    portrait = Image.new("RGB", (1240, 1754), "white")
    landscape = Image.new("RGB", (1754, 1240), "white")

    p_w, p_controls, p_pane, p_img = await measure(portrait)
    l_w, _, _, _ = await measure(landscape)

    # Load-bearing: the pane width *tracks the page aspect*. A landscape page is
    # wider than a portrait one, so its pane is wider — a fixed-fraction pane
    # (the pre-pin behaviour) would give the SAME width for both, so this catches
    # a regression that drops the runtime pin.
    assert l_w > p_w

    # Portrait specifics: pane far short of the 120-col screen, #controls gets the
    # rest (>= the floor), pane hugs the image (thin gutter), image contained.
    assert p_img.width > 0 and p_img.height > 0
    assert p_w < 100
    assert p_controls >= PagePreview._MIN_CONTROLS_WIDTH
    assert 0 <= p_pane.width - p_img.width <= 8


# --- Fit / 100% zoom toggle (UTILS-15) ---------------------------------------


def test_mode_defaults_to_fit():
    # Zoom defaults to Fit (aspect-contained).
    from pdf_crop.features.crop.preview import FIT

    preview = PagePreview(total=3)
    assert preview.mode == FIT


def test_toggle_zoom_flips_fit_and_native():
    # toggle_zoom alternates Fit <-> 100% without needing a mount.
    from pdf_crop.features.crop.preview import FIT, NATIVE

    preview = PagePreview(total=3)
    preview.toggle_zoom()
    assert preview.mode == NATIVE
    preview.toggle_zoom()
    assert preview.mode == FIT


async def test_toggle_resizes_image_native_in_100_contained_in_fit(
    three_page_pdf, monkeypatch
):
    # Toggling to 100% sizes the image to its *native* cell size (1 image pixel ~=
    # 1 terminal pixel), which exceeds the Fit (contained) size; toggling back
    # restores the contained size. We feed a portrait image whose native size is
    # known: at the headless cell geometry (10x20 px/cell) a 400x1600 image is
    # 40x80 cells, far larger than its contained Fit size, so the difference is
    # unambiguous.
    from pdf_crop.app import PdfCropApp
    from textual_image._terminal import get_cell_size
    from textual_image.widget import Image as ImageWidget

    portrait = Image.new("RGB", (400, 1600), "white")

    def fake_render(self, page_number):
        return portrait

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()

        image = preview.query_one("#preview_image", ImageWidget)
        fit_size = image.content_size
        assert fit_size.width > 0 and fit_size.height > 0

        preview.toggle_zoom()  # -> 100%
        await _settle_renders(app, pilot)
        await pilot.pause()
        native = image.content_size
        # Native cell size derived from the source pixels and the cell geometry.
        cell = get_cell_size()
        assert native.width == round(portrait.width / cell.width)
        assert native.height == round(portrait.height / cell.height)
        # 100% is bigger than the contained Fit size (so it can be scrolled).
        assert native.height > fit_size.height
        assert native.width > fit_size.width

        preview.toggle_zoom()  # -> Fit
        await _settle_renders(app, pilot)
        await pilot.pause()
        assert image.content_size == fit_size


async def test_100_percent_is_scrollable_fit_is_not(three_page_pdf, monkeypatch):
    # The crux: in 100% the image overflows the scroll container's viewport — the
    # image region exceeds the viewport and the scroll bounds (max_scroll_x/y) are
    # positive, so it can be panned both ways. In Fit the contained image fits the
    # viewport, so there's nothing to scroll.
    from pdf_crop.app import PdfCropApp
    from textual.containers import ScrollableContainer
    from textual_image.widget import Image as ImageWidget

    portrait = Image.new("RGB", (400, 1600), "white")

    def fake_render(self, page_number):
        return portrait

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()

        scroll = preview.query_one("#preview_scroll", ScrollableContainer)
        image = preview.query_one("#preview_image", ImageWidget)
        viewport = scroll.content_size
        assert viewport.width > 0 and viewport.height > 0

        # Fit: contained, nothing to scroll.
        assert scroll.max_scroll_y == 0
        assert scroll.max_scroll_x == 0
        assert image.region.height <= viewport.height

        preview.toggle_zoom()  # -> 100%
        await _settle_renders(app, pilot)
        await pilot.pause()
        # The image region now exceeds the viewport in both dimensions, and the
        # scroll container reports positive scroll range on both axes — pannable.
        assert image.content_size.height > viewport.height
        assert image.content_size.width > viewport.width
        assert scroll.max_scroll_y > 0
        assert scroll.max_scroll_x > 0


async def test_pane_width_is_stable_across_modes(three_page_pdf, monkeypatch):
    # HARD constraint: toggling Fit <-> 100% must not reflow the #preview /
    # #controls split. The pane is pinned to the Fit width and a native-size page
    # scrolls *inside* it, so the pane (and #controls) keep the same width in both
    # modes even though the native page is far larger than the pane.
    from pdf_crop.app import PdfCropApp

    portrait = Image.new("RGB", (400, 1600), "white")

    def fake_render(self, page_number):
        return portrait

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        controls = app.screen.query_one("#controls")
        await _settle_renders(app, pilot)
        await pilot.pause()

        fit_pane_w = preview.region.width
        fit_controls_w = controls.region.width
        assert fit_pane_w > 0

        preview.toggle_zoom()  # -> 100% (native page much wider than the pane)
        await _settle_renders(app, pilot)
        await pilot.pause()
        # Bounded: the pane did NOT widen to the native page, and #controls was
        # not squeezed — both widths are unchanged.
        assert preview.region.width == fit_pane_w
        assert controls.region.width == fit_controls_w

        preview.toggle_zoom()  # -> Fit again
        await _settle_renders(app, pilot)
        await pilot.pause()
        assert preview.region.width == fit_pane_w
        assert controls.region.width == fit_controls_w


async def test_100_percent_preserves_aspect_ratio(three_page_pdf, monkeypatch):
    # Native size must not distort: the image's cell ratio matches the source
    # pixel ratio (within the rounding to whole cells at the headless 10x20 cell
    # geometry). A landscape page is used so a ratio-mangling regression (e.g.
    # pinning to a square) would be caught.
    from pdf_crop.app import PdfCropApp
    from textual_image._terminal import get_cell_size
    from textual_image.widget import Image as ImageWidget

    landscape = Image.new("RGB", (1600, 400), "white")  # 4:1

    def fake_render(self, page_number):
        return landscape

    monkeypatch.setattr(PagePreview, "_render_page_image", fake_render)

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        await _settle_renders(app, pilot)
        await pilot.pause()
        preview.toggle_zoom()  # -> 100%
        await _settle_renders(app, pilot)
        await pilot.pause()

        image = preview.query_one("#preview_image", ImageWidget)
        cell = get_cell_size()
        # Native cells are the source pixels divided by the cell geometry; this is
        # an exact aspect-preserving map (no stretch to a pinned box).
        assert image.content_size.width == round(landscape.width / cell.width)
        assert image.content_size.height == round(landscape.height / cell.height)
