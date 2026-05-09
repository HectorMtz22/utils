from pathlib import Path


def resolve(src: Path, suffix: str = "_cropped") -> Path:
    """Return a non-colliding output path next to src.

    First tries `<stem><suffix>.pdf`. If that exists, appends ` (1)`,
    ` (2)`, ... until a free name is found.
    """
    base = src.with_name(f"{src.stem}{suffix}.pdf")
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = src.with_name(f"{src.stem}{suffix} ({n}).pdf")
        if not candidate.exists():
            return candidate
        n += 1
