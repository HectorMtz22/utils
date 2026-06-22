import threading
from collections import OrderedDict
from pathlib import Path

import fitz
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static
from textual_image._geometry import ImageSize
from textual_image._terminal import get_cell_size
from textual_image.widget import Image

from pdf_crop.shared import imaging

# A page only needs to be legible in the pane, not print-sharp; 150 dpi keeps
# the rasterize fast while staying crisp under the terminal graphics protocols.
PREVIEW_DPI = 150

# How many rendered pages to keep so revisits are instant. A handful of pages
# either side of the current one covers typical back-and-forth navigation
# without holding a large document's worth of rasters in memory. This bounds the
# page *count*, not bytes: each entry is a PREVIEW_DPI raster (~6 MB for A4 at
# 150 dpi), so total memory scales with page size.
RENDER_CACHE_SIZE = 16

# Zoom modes. "fit" aspect-contains the page in the pane (the #36/#38 fix:
# width/height both `auto`); "100%" shows the page at its native pixel size
# (1 image pixel ~= 1 terminal pixel) and lets the scroll container pan over it.
FIT = "fit"
NATIVE = "100%"


class PagePreview(Vertical):
    """Right-pane page navigator that renders the current page as an image.

    Owns a 1-based `current` page index and the document `total`. A threaded,
    exclusive worker rasterizes the current page (fitz -> PIL) and hands the
    image to a `textual-image` widget on the main thread, so fast navigation
    cancels stale renders. Render failures show an inline message rather than
    crashing the app.
    """

    current: reactive[int] = reactive(1)
    # Zoom mode. Default Fit: the page is aspect-contained in the pane. Toggling
    # to 100% shows it at native pixel size and the scroll container pans over it.
    mode: reactive[str] = reactive(FIT)

    def __init__(self, *, total: int, src: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.total = max(1, total)
        self.src = src
        self._included_pages: set[int] = set()
        # The PIL image currently shown, kept so a mode toggle can re-size the
        # widget (Fit <-> native) without re-rendering the page.
        self._current_image = None
        # Bounded LRU cache of rendered images keyed by (page_number, dpi). Only
        # ever touched on the main thread, so it needs no lock of its own. Named
        # `_preview_cache` (not `_render_cache`) to avoid clobbering textual's
        # own `Widget._render_cache`, which it reassigns during layout/render.
        self._preview_cache: OrderedDict[tuple[int, int], object] = OrderedDict()
        # The document is opened once (lazily) and reused across renders. The
        # lock guards the shared fitz handle: renders read it on the worker
        # thread, and unmount closes it on the main thread — closing while a
        # render is mid-read would be a use-after-free on a C object.
        self._doc: fitz.Document | None = None
        self._doc_lock = threading.Lock()

    def compose(self) -> ComposeResult:
        with Horizontal(id="preview_nav"):
            yield Button("< prev", id="prev_btn")
            yield Static("", id="preview_status")
            yield Button("next >", id="next_btn")
        # The image lives in a scroll container so a page larger than the pane
        # (always, in 100% mode; a tall page even in Fit) can be panned with the
        # arrows / scroll wheel / scrollbars instead of being clipped.
        with ScrollableContainer(id="preview_scroll"):
            yield Image(id="preview_image")
        yield Static("", id="preview_message")

    def on_mount(self) -> None:
        self._refresh_status()
        self._render_current()

    def on_unmount(self) -> None:
        # Close the shared doc, but only when no render is reading it. A render
        # holds the lock for the duration of its read, so acquire non-blockingly:
        # if a render has it, leave the doc alone (the next unmount, or process
        # exit, reclaims it) rather than free a C object mid-read. Acquiring
        # succeeds means it's safe to close.
        if self._doc_lock.acquire(blocking=False):
            try:
                if self._doc is not None:
                    self._doc.close()
                    self._doc = None
            finally:
                self._doc_lock.release()

    # --- zoom mode ------------------------------------------------------------

    def _zoom_label(self) -> str:
        """Button caption: shows the mode you'd switch *to* (the action)."""
        return "100%" if self.mode == FIT else "Fit"

    def toggle_zoom(self) -> None:
        """Flip Fit <-> 100%."""
        self.mode = NATIVE if self.mode == FIT else FIT

    def watch_mode(self) -> None:
        # Re-size the currently shown image to the new mode and update the
        # toggle's caption. The toggle button now lives in the screen's action
        # bar (UTILS-16), not inside this pane, so look it up via `self.screen`.
        # Guarded: `mode` may be set before mount, and standalone-widget tests
        # have no screen / no zoom_btn.
        try:
            self.screen.query_one("#zoom_btn", Button).label = self._zoom_label()
        except Exception:
            pass  # not mounted yet, or no zoom button (standalone widget)
        if self._current_image is not None:
            self._apply_mode_sizing(self._current_image)

    # --- navigation (all clamp to [1, total]) ---------------------------------

    def goto(self, n: int) -> None:
        self.current = max(1, min(n, self.total))

    def next(self) -> None:
        self.goto(self.current + 1)

    def prev(self) -> None:
        self.goto(self.current - 1)

    # --- inclusion badge ------------------------------------------------------

    def included(self, pages: set[int]) -> bool:
        """Is the current page in the given selected-page set?"""
        return self.current in pages

    def set_selected(self, pages: set[int]) -> None:
        """Record the selected pages so the badge tracks the live range."""
        self._included_pages = pages
        self._refresh_status()

    def watch_current(self) -> None:
        self._refresh_status()
        # `current` can change before mount (e.g. unit tests drive goto/next
        # directly); only render once we're mounted with a worker host.
        if self.is_mounted:
            self._render_current()

    def _render_current(self) -> None:
        """Show the current page from cache if possible, else render it.

        A cache hit (checked here on the main thread) displays immediately and
        skips the worker; a miss spawns the threaded render as before.
        """
        page_number = self.current
        cached = self._cache_get(page_number)
        if cached is not None:
            self._render_done(cached, page_number, cache=False)
        else:
            self._render_worker()

    def _cache_get(self, page: int):
        """Return the cached image for `page` (at the preview dpi), or None.

        A hit promotes the entry to most-recently-used so it survives eviction.
        """
        key = (page, PREVIEW_DPI)
        image = self._preview_cache.get(key)
        if image is not None:
            self._preview_cache.move_to_end(key)
        return image

    def _cache_put(self, page: int, image) -> None:
        """Cache `image` for `page` and evict the least-recently-used over cap.

        The cap is read from the module global at eviction time so it can be
        tuned (or overridden in tests) without re-instantiating the widget.
        """
        self._preview_cache[(page, PREVIEW_DPI)] = image
        self._preview_cache.move_to_end((page, PREVIEW_DPI))
        while len(self._preview_cache) > RENDER_CACHE_SIZE:
            self._preview_cache.popitem(last=False)

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#preview_status", Static)
        except Exception:
            return  # not mounted yet
        state = "included" if self.included(self._included_pages) else "excluded"
        colour = "green" if state == "included" else "red"
        status.update(
            f"Page {self.current}/{self.total} — [{colour}]{state}[/{colour}]"
        )

    # --- page image render (threaded, exclusive) ------------------------------

    def _ensure_doc(self) -> "fitz.Document":
        """Open the document once and reuse the handle on later calls.

        Acquires `_doc_lock` so two callers can't both open it, and so unmount
        can't close it mid-open.
        """
        with self._doc_lock:
            return self._open_locked()

    def _open_locked(self) -> "fitz.Document":
        """Open the doc if needed and return it. Caller MUST hold `_doc_lock`."""
        if self._doc is None:
            self._doc = fitz.open(str(self.src))
        return self._doc

    def _render_page_image(self, page_number: int):
        """Rasterize 1-based `page_number` to a PIL image. The mockable boundary.

        Reads from the shared document (opened once, reused) so navigation
        doesn't re-parse the PDF on every page. The open and the read happen
        under a single `_doc_lock` acquisition, and unmount frees the doc under
        the same lock, so it can never be closed mid-read — a use-after-free on
        a C object, not a catchable Python error. The returned PIL image owns
        its own pixels.
        """
        with self._doc_lock:
            doc = self._open_locked()
            return imaging.render_page(doc[page_number - 1], dpi=PREVIEW_DPI)

    @work(thread=True, exclusive=True, group="preview-render")
    def _render_worker(self) -> None:
        if self.src is None:
            return
        page_number = self.current
        try:
            self._show_loading()
            image = self._render_page_image(page_number)
        except Exception as e:  # never let a render error escape and crash the app
            self.app.call_from_thread(self._render_failed, e)
            return
        # Pass the page we actually rendered (not `self.current`, which may have
        # moved on under fast navigation) so the cache keys it correctly.
        self.app.call_from_thread(self._render_done, image, page_number)

    def _show_loading(self) -> None:
        try:
            self.app.call_from_thread(
                self.query_one("#preview_message", Static).update,
                "[dim]Rendering…[/dim]",
            )
        except Exception:
            return  # not mounted yet

    def _render_done(self, image, page_number: int, *, cache: bool = True) -> None:
        # Cache the freshly rendered image (keyed by the page it depicts) so a
        # later revisit is instant; the cache-hit path passes `cache=False`
        # since the image is already stored.
        if cache:
            self._cache_put(page_number, image)
        self._current_image = image
        try:
            self.query_one("#preview_image", Image).image = image
            self.query_one("#preview_message", Static).update("")
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)
        # Reset the scroll position so a new page starts at the top-left rather
        # than wherever the previous page was panned to.
        try:
            self.query_one("#preview_scroll", ScrollableContainer).scroll_home(
                animate=False
            )
        except Exception:
            pass
        self._apply_mode_sizing(image)

    # --- per-mode sizing ------------------------------------------------------

    def _apply_mode_sizing(self, image) -> None:
        """Size `#preview_image` for the current mode and pin the pane width.

        Fit: both dimensions `auto` so textual-image aspect-contains the page in
        the pane (never pin both *to cells* — that distorts; the #36/#38 fix).
        100%: explicit native cell dims so 1 image pixel ~= 1 terminal pixel and
        the page overflows the pane, letting the scroll container pan over it.

        The pane is pinned to the Fit width so toggling Fit<->100% keeps the
        #preview / #controls split stable: a native-size page scrolls *inside*
        the fixed pane rather than pushing it wider and squeezing #controls.
        """
        try:
            img_widget = self.query_one("#preview_image", Image)
        except Exception:
            return  # not mounted yet
        if self.mode == NATIVE:
            cell = get_cell_size()
            img_widget.styles.width = max(1, round(image.width / cell.width))
            img_widget.styles.height = max(1, round(image.height / cell.height))
        else:
            img_widget.styles.width = "auto"
            img_widget.styles.height = "auto"
            self._pin_pane_to_fit(image)

    # The pane's own chrome: round border (1 col each side) + `padding: 0 1`
    # (1 col each side) = 4 columns of width that aren't part of the image area.
    _PANE_CHROME = 4
    # Columns the controls pane keeps even when the preview hugs a very wide
    # page. Without a floor, a landscape page would expand the pane far enough to
    # squeeze the range input / checkboxes to an unusable sliver. Portrait and
    # mildly-landscape pages don't reach this cap.
    _MIN_CONTROLS_WIDTH = 36

    def on_resize(self) -> None:
        # Layout has run (or re-run): the pane/body now have real sizes, so the
        # Fit pin can be computed accurately. _render_done runs *before* the
        # first layout (sizes are still 0x0), so this is where the pane actually
        # gets hugged to the page. Re-pinning to the same width is a no-op (the
        # style is only touched when it changes), so this converges and doesn't
        # loop. Only in Fit: in 100% the pane width is held fixed.
        if self.mode == FIT and self._current_image is not None:
            self._pin_pane_to_fit(self._current_image)

    def _pin_pane_to_fit(self, image) -> None:
        """Pin `#preview` width so the frame hugs the Fit-sized page.

        Computes the cell width textual-image would give the page when contained
        in the pane (same `ImageSize` math the widget uses), then sets the pane
        width to that plus its border+padding. Done in Fit only; in 100% the pane
        keeps this width so the page scrolls within a bounded box.

        Bails until layout has resolved a real band height — before then the
        widget reports 0x0 and the fit math would be starved (see `on_resize`,
        which re-pins once sizes are real). The available *width* is bounded by
        the body (the parent split), not by the pane's own current width, so a
        wide page that comes after a narrow one can re-expand the pane, and so a
        width-bound page can't push the pane past the screen and squeeze
        #controls to nothing.
        """
        avail_h = self.content_size.height
        avail_w = self._available_pane_width()
        if avail_h <= 0 or avail_w <= 0:
            return  # not laid out yet; on_resize will re-pin
        cell = get_cell_size()
        fit_w, _ = ImageSize(image.width, image.height, "auto", "auto").get_cell_size(
            avail_w, avail_h, cell
        )
        target = fit_w + self._PANE_CHROME
        # Idempotent: only touch the style when it changes, so the resize this
        # triggers settles instead of bouncing.
        if self.styles.width is None or self.styles.width.value != target:
            self.styles.width = target

    def _available_pane_width(self) -> int:
        """Inner image width the pane may occupy: body width minus chrome.

        Reserves a few columns so #controls never collapses entirely. Returns 0
        before the body has a measured size (the caller then defers).
        """
        parent = self.parent
        body_w = getattr(getattr(parent, "content_size", None), "width", 0) or 0
        if body_w <= 0:
            return 0
        # Keep #controls usable; the pane gets whatever's left for the image.
        return max(1, body_w - self._PANE_CHROME - self._MIN_CONTROLS_WIDTH)

    def _render_failed(self, error: Exception) -> None:
        try:
            self.query_one("#preview_message", Static).update(
                f"[red]Preview unavailable: {error}[/red]"
            )
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)
