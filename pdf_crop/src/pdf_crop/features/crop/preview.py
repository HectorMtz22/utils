import threading
from collections import OrderedDict
from pathlib import Path

import fitz
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static
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


class PagePreview(Vertical):
    """Right-pane page navigator that renders the current page as an image.

    Owns a 1-based `current` page index and the document `total`. A threaded,
    exclusive worker rasterizes the current page (fitz -> PIL) and hands the
    image to a `textual-image` widget on the main thread, so fast navigation
    cancels stale renders. Render failures show an inline message rather than
    crashing the app.
    """

    current: reactive[int] = reactive(1)

    def __init__(self, *, total: int, src: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.total = max(1, total)
        self.src = src
        self._included_pages: set[int] = set()
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
        try:
            self.query_one("#preview_image", Image).image = image
            self.query_one("#preview_message", Static).update("")
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)

    def _render_failed(self, error: Exception) -> None:
        try:
            self.query_one("#preview_message", Static).update(
                f"[red]Preview unavailable: {error}[/red]"
            )
        except Exception:
            return  # widget gone (e.g. unmounted mid-render)
