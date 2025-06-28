import os
import threading
import time
import json
from flask import Flask, request, jsonify, render_template
from pytube import YouTube
import pygame
import yt_dlp

app = Flask(__name__)

print(f"Current working directory: {os.getcwd()}")  # Debug print

queue = []
priority_queue = []
current_song = None
current_position = 0
is_paused = False
duration = 0
skip_event = threading.Event()

AUDIO_DIR = "audio_files"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Initialize pygame mixer
pygame.mixer.init()


def download_audio(video_id):
    """Download audio from YouTube using yt_dlp."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        file_path = os.path.join(AUDIO_DIR, f"{video_id}.mp3")
        if not os.path.exists(file_path):
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.splitext(file_path)[0],  # Remove extension to avoid duplication
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Unknown Title")
                return file_path, title
        else:
            return file_path, "Cached Audio"
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None, None


def play_song(song):
    global current_song, is_paused, current_position, duration
    current_song = song
    is_paused = False
    current_position = 0

    file_path, title = download_audio(song["videoId"])
    file_path = os.path.abspath(file_path)  # Convert to absolute path
    print(f"Attempting to play file: {file_path}")  # Debug print

    if not file_path or not os.path.exists(file_path):  # Check if file exists
        print(f"Error: File not found or invalid format for song {song['videoId']}. Skipping...")
        print(f"Expected file path: {file_path}")  # Debug print
        print(f"Contents of AUDIO_DIR: {os.listdir(AUDIO_DIR)}")  # Debug print
        return

    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    duration = pygame.mixer.Sound(file_path).get_length()

    while pygame.mixer.music.get_busy():
        if skip_event.is_set():
            pygame.mixer.music.stop()
            skip_event.clear()
            break
        if not is_paused:
            current_position += 1
        time.sleep(1)

    current_song = None
    current_position = 0
    duration = 0


def playback_thread():
    while True:
        if not current_song:
            next_song = priority_queue.pop(0) if priority_queue else (queue.pop(0) if queue else None)
            if next_song:
                play_song(next_song)
            else:
                time.sleep(1)
        else:
            time.sleep(1)


def download_queue_thread():
    """Background thread to download songs in the queue."""
    while True:
        for song in queue + priority_queue:
            video_id = song["videoId"]
            file_path = os.path.join(AUDIO_DIR, f"{video_id}.mp3")
            if not os.path.exists(file_path):
                download_audio(video_id)
        time.sleep(5)


@app.route("/pause", methods=["POST"])
def pause():
    global is_paused
    if current_song and not is_paused:
        pygame.mixer.music.pause()
        is_paused = True
        return jsonify({"status": "paused"})
    return jsonify({"status": "no_song_playing"})


@app.route("/resume", methods=["POST"])
def resume():
    global is_paused
    if current_song and is_paused:
        pygame.mixer.music.unpause()
        is_paused = False
        return jsonify({"status": "resumed"})
    return jsonify({"status": "no_song_playing"})


@app.route("/skip", methods=["POST"])
def skip_song():
    if current_song:
        skip_event.set()
        return jsonify({"status": "skipped"})
    return jsonify({"status": "no_song_playing"})


@app.route("/queue/add", methods=["POST"])
def add_to_queue():
    data = request.json
    song = data.get("song")
    if not song:
        return jsonify({"error": "Missing song"}), 400

    queue.append(song)
    return jsonify({"status": "added", "queue": queue})


@app.route("/queue/priority/add", methods=["POST"])
def add_to_priority_queue():
    data = request.json
    song = data.get("song")
    if not song:
        return jsonify({"error": "Missing song"}), 400

    priority_queue.append(song)
    return jsonify({"status": "added", "priority_queue": priority_queue})


@app.route("/queue/all")
def get_queues():
    return jsonify({
        "queue": queue,
        "priority": priority_queue
    })


@app.route("/status")
def status():
    return jsonify({
        "current_song": current_song,
        "position": current_position,
        "duration": duration,
        "paused": is_paused
    })


@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"results": []})

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "force_generic_extractor": True,
        "default_search": "ytsearch5"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(query, download=False)
            entries = result.get("entries", [])
            songs = []
            for entry in entries:
                video_id = entry.get("id")
                title = entry.get("title")
                if video_id and title:
                    songs.append({"videoId": video_id, "title": title})
            return jsonify({"results": songs})
        except Exception as e:
            print(f"Search error: {e}")
            return jsonify({"results": []})


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    threading.Thread(target=playback_thread, daemon=True).start()
    threading.Thread(target=download_queue_thread, daemon=True).start()
    try:
        app.run(debug=True, use_reloader=False)  # Disable reloader to avoid threading issues
    except KeyboardInterrupt:
        print("Shutting down server...")
