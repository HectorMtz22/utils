import os
import re
import requests
from mutagen.flac import FLAC
from mutagen.id3 import ID3

MUSIC_DIR = "/Volumes/music-library"  # ajusta esto

def clean_title(title):
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\[.*?\]', '', title)
    return title.strip()

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

def get_lrc(artist, title):
    try:
        r = requests.get("https://lrclib.net/api/get", params={
            "artist_name": artist,
            "track_name": title,
        }, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("syncedLyrics") or data.get("plainLyrics")
    except:
        pass
    return None

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

        lyrics = get_lrc(artist, clean)

        if lyrics:
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write(lyrics)
            print(f"✓ Descargado")
        else:
            print(f"✗ No encontrado")
