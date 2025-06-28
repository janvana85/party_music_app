# Audio Downloader

This script downloads audio from YouTube videos. It uses `pytube` as the primary library and falls back to `yt-dlp` if `pytube` fails.

## Requirements

- Python 3.7+
- `pytube`
- `yt-dlp`

## Installation

Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Place the script in your desired directory.
2. Call the `download_audio(video_id)` function with a valid YouTube video ID.
3. The audio file will be saved in the `audio_files` directory.

## Features

- Validates video IDs before downloading.
- Automatically falls back to `yt-dlp` if `pytube` encounters an error.
- Logs errors and download status for debugging.
