# music-lyrics

Fetches synced lyrics for a local FLAC/MP3 library and writes a `.lrc` file next
to each track.

[lrclib.net](https://lrclib.net) is tried first, then
[NetEase Cloud Music](https://music.163.com) as a fallback. Only **synced**
(timestamped) lyrics are written — tracks where only plain lyrics exist are
reported as warnings rather than written.

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

