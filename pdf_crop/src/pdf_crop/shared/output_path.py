from pathlib import Path

from pdf_crop.shared.errors import OutputPathError


def _non_colliding(directory: Path, stem: str) -> Path:
    """Return a non-colliding `<stem>.pdf` path inside directory.

    First tries `<stem>.pdf`. If that exists, appends ` (1)`, ` (2)`, ... until
    a free name is found.
    """
    base = directory / f"{stem}.pdf"
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = directory / f"{stem} ({n}).pdf"
        if not candidate.exists():
            return candidate
        n += 1


def resolve(src: Path, output: str | None = None, *, suffix: str = "_cropped") -> Path:
    """Return a non-colliding output path for the cropped PDF.

    `output` is None (or blank/whitespace-only) -> `<src.parent>/<src.stem>
    <suffix>.pdf` (today's behavior, unchanged). Otherwise the `.pdf` suffix
    (case-insensitive) is the only signal: a `.pdf`-suffixed value is a **file
    target** (its parent dir + its exact name, no `<suffix>` appended); anything
    else is a **folder target** (the default `<src.stem><suffix>.pdf` written
    inside it). `~` is expanded and missing directories are created. `mkdir`
    failures (a parent that's a regular file, permission denied, ...) raise
    OutputPathError.
    """
    # A blank value (`-o ""`, an unset shell var) means "no override" — not
    # Path(".")/the cwd. Normalizing here keeps CLI and TUI semantics identical.
    if output is not None and not output.strip():
        output = None
    if output is None:
        directory = src.parent
        stem = f"{src.stem}{suffix}"
    else:
        value = Path(output).expanduser()
        if value.suffix.lower() == ".pdf":
            directory = value.parent
            stem = value.stem
        else:
            directory = value
            stem = f"{src.stem}{suffix}"

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OutputPathError(f"could not prepare output directory: {directory}: {e}") from e

    return _non_colliding(directory, stem)
