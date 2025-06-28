import requests
import subprocess
import time

BACKEND_URL = "http://localhost:5000"

def get_next_song():
    try:
        resp = requests.get(f"{BACKEND_URL}/queue/next")
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "next":
            return data["song"]
        return None
    except Exception as e:
        print("Error getting next song:", e)
        return None

def play_song(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Playing: {url}")
    subprocess.run(["mpv", "--no-terminal", url])

def main_loop():
    print("Starting player loop...")
    while True:
        song = get_next_song()
        if not song:
            print("Queue is empty, waiting 5 seconds...")
            time.sleep(5)
            continue
        play_song(song["videoId"])

if __name__ == "__main__":
    main_loop()
