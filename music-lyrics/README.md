# music-lyrics

Fetches synced/plain lyrics from [lrclib.net](https://lrclib.net) for a local FLAC/MP3 library. Writes a `.lrc` file next to each track.

```bash
uv sync
export MUSIC_DIR=/path/to/your/music   # default: /Volumes/music-library
uv run python lyrics_on_nas.py
```

## Develop

```bash
uv sync
uv run pytest
```

