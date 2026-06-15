from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static


class PagePreview(Vertical):
    """Right-pane page navigator with an included/excluded badge.

    Owns a 1-based `current` page index and the document `total`. The actual
    rendered page image is a separate issue (UTILS-5); for now the pane shows a
    text placeholder where the image will go.
    """

    current: reactive[int] = reactive(1)

    def __init__(self, *, total: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.total = max(1, total)
        self._included_pages: set[int] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="preview_nav"):
            yield Button("< prev", id="prev_btn")
            yield Static("", id="preview_status")
            yield Button("next >", id="next_btn")
        yield Static(
            "[dim](page image preview coming soon)[/dim]",
            id="preview_image",
        )

    def on_mount(self) -> None:
        self._refresh_status()

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
