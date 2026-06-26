import os
import re
import requests
from mutagen.flac import FLAC
from mutagen.id3 import ID3

MUSIC_DIR = os.environ.get("MUSIC_DIR", "/Volumes/music-library")

NETEASE_HEADERS = {
    "Referer": "https://music.163.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

def clean_title(title):
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\[.*?\]', '', title)
    return title.strip()

def is_synced(text):
    if not text:
        return False
    return bool(re.search(r'\[\d{1,2}:\d{2}', text))

def is_placeholder_lyric(text):
    # NetEase returns instrumental/metadata-only bodies that still carry
    # timestamps; reject them so we don't write junk .lrc files.
    if "纯音乐" in text:  # instrumental marker ("pure music")
        return True
    return not re.sub(r'\[[^\]]*\]', '', text).strip()

def get_tags(filepath):
    try:
        if filepath.endswith(".flac"):
            audio = FLAC(filepath)
            artist = audio.get("artist", [""])[0]
            title = audio.get("title", [""])[0]
        elif filepath.endswith(".mp3"):
            audio = ID3(filepath)
            artist = str(audio.get("TPE1", ""))
            title = str(audio.get("TIT2", ""))
        else:
            return None, None
        return artist, title
    except:
        return None, None

def fetch_lrclib(artist, title):
    try:
        r = requests.get("https://lrclib.net/api/get", params={
            "artist_name": artist,
            "track_name": title,
        }, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("syncedLyrics"), data.get("plainLyrics")
    except:
        pass
    return None, None

def fetch_netease(artist, title):
    try:
        r = requests.get("https://music.163.com/api/search/get", params={
            "s": f"{artist} {title}",
            "type": 1,
            "limit": 5,
        }, headers=NETEASE_HEADERS, timeout=10)
        if r.status_code != 200:
            return None, None
        songs = (r.json().get("result") or {}).get("songs") or []
        if not songs:
            return None, None
        song_id = songs[0]["id"]

        r = requests.get("https://music.163.com/api/song/lyric", params={
            "id": song_id,
            "lv": -1,
            "kv": -1,
            "tv": -1,
        }, headers=NETEASE_HEADERS, timeout=10)
        if r.status_code != 200:
            return None, None
        lyric = ((r.json().get("lrc") or {}).get("lyric") or "").strip()
        if not lyric or is_placeholder_lyric(lyric):
            return None, None
        if is_synced(lyric):
            return lyric, None
        return None, lyric
    except:
        return None, None

def resolve_synced(artist, title):
    synced, plain = fetch_lrclib(artist, title)
    if synced:
        return synced, "lrclib"
    if plain:
        print("⚠ Solo letra plana en lrclib")
    synced, plain = fetch_netease(artist, title)
    if synced:
        return synced, "NetEase"
    if plain:
        print("⚠ Solo letra plana en NetEase")
    return None, None

def main():
    for root, dirs, files in os.walk(MUSIC_DIR):
        for file in files:
            if not file.endswith((".flac", ".mp3")):
                continue

            filepath = os.path.join(root, file)
            lrc_path = os.path.splitext(filepath)[0] + ".lrc"

            if os.path.exists(lrc_path):
                print(f"✓ Ya existe: {file}")
                continue

            artist, title = get_tags(filepath)
            if not artist or not title:
                print(f"✗ Sin tags: {file}")
                continue

            clean = clean_title(title)
            print(f"→ Buscando: {artist} - {clean}")

            synced, source = resolve_synced(artist, clean)

            if synced:
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(synced)
                print(f"✓ Descargado ({source})")
            else:
                print(f"✗ No encontrado")

if __name__ == "__main__":
    main()
