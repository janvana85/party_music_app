const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const ytdl = require('ytdl-core');
const fs = require('fs');
const path = require('path');
const ytsr = require('ytsr'); // Add this to handle YouTube search

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const AUDIO_DIR = path.join(__dirname, 'audio_files');
if (!fs.existsSync(AUDIO_DIR)) fs.mkdirSync(AUDIO_DIR);

let queue = [];
let priorityQueue = [];
let currentSong = null;
let isPaused = false;
let currentPosition = 0;
let duration = 0;
let playbackInterval = null;

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Serve the frontend
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Serve audio files with range support
app.get('/audio/:videoId', (req, res) => {
    const filePath = path.join(AUDIO_DIR, `${req.params.videoId}.mp3`);
    if (!fs.existsSync(filePath)) {
        return res.status(404).send({ error: 'Audio file not found' });
    }

    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    const range = req.headers.range;

    if (range) {
        const parts = range.replace(/bytes=/, '').split('-');
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

        if (start >= fileSize || end >= fileSize) {
            return res.status(416).send('Requested range not satisfiable');
        }

        const chunkSize = end - start + 1;
        const file = fs.createReadStream(filePath, { start, end });
        const head = {
            'Content-Range': `bytes ${start}-${end}/${fileSize}`,
            'Accept-Ranges': 'bytes',
            'Content-Length': chunkSize,
            'Content-Type': 'audio/mpeg',
        };

        res.writeHead(206, head);
        file.pipe(res);
    } else {
        const head = {
            'Content-Length': fileSize,
            'Content-Type': 'audio/mpeg',
        };

        res.writeHead(200, head);
        fs.createReadStream(filePath).pipe(res);
    }
});

// Search for videos on YouTube
app.get('/search', async (req, res) => {
    const query = req.query.q;
    if (!query) return res.status(400).send({ error: 'Query is required' });

    try {
        const searchResults = await ytsr(query, { limit: 10 });
        const videos = searchResults.items
            .filter(item => item.type === 'video' && item.id) // Ensure valid video items
            .map(video => ({
                title: video.title,
                videoId: video.id,
                duration: video.duration || 'Unknown',
                thumbnail: video.bestThumbnail.url || '',
            }));
        res.send(videos);
    } catch (error) {
        console.error('Error during search:', error);
        res.status(500).send({ error: 'Failed to search videos. Please try again later.' });
    }
});

// Download audio from YouTube
async function downloadAudio(videoId) {
    const filePath = path.join(AUDIO_DIR, `${videoId}.mp3`);
    if (fs.existsSync(filePath)) return filePath;

    try {
        const stream = ytdl(`https://www.youtube.com/watch?v=${videoId}`, { filter: 'audioonly' });
        const writeStream = fs.createWriteStream(filePath);
        stream.pipe(writeStream);

        await new Promise((resolve, reject) => {
            stream.on('error', (error) => {
                console.error(`Error in ytdl stream for videoId ${videoId}:`, error);
                reject(error);
            });
            writeStream.on('finish', resolve);
            writeStream.on('error', reject);
        });

        return filePath;
    } catch (error) {
        console.error(`Error downloading audio for videoId ${videoId}:`, error);
        return null; // Return null to indicate failure
    }
}

// Play the next song
async function playNextSong() {
    if (priorityQueue.length > 0) {
        currentSong = priorityQueue.shift();
    } else if (queue.length > 0) {
        currentSong = queue.shift();
    } else {
        currentSong = null;
        io.emit('nowPlaying', { currentSong: null });
        return;
    }

    const filePath = await downloadAudio(currentSong.videoId);
    if (!filePath) {
        playNextSong();
        return;
    }

    duration = 0; // Reset duration
    currentPosition = 0;
    isPaused = false;

    io.emit('nowPlaying', { currentSong, audioUrl: `/audio/${currentSong.videoId}` });
}

// Socket.io events
io.on('connection', (socket) => {
    console.log('A user connected');

    // Send initial status
    socket.emit('status', { currentSong, queue, priorityQueue, isPaused, currentPosition, duration });

    // Add song to queue
    socket.on('addToQueue', (song) => {
        queue.push(song);
        io.emit('queueUpdated', { queue, priorityQueue });

        // Automatically start playing if no song is currently playing
        if (!currentSong) {
            playNextSong();
        }
    });

    // Add song to priority queue
    socket.on('addToPriorityQueue', (song) => {
        priorityQueue.push(song);
        io.emit('queueUpdated', { queue, priorityQueue });

        // Automatically start playing if no song is currently playing
        if (!currentSong) {
            playNextSong();
        }
    });

    // Pause playback
    socket.on('pause', () => {
        isPaused = true;
        io.emit('paused');
    });

    // Resume playback
    socket.on('resume', () => {
        isPaused = false;
        io.emit('resumed');
    });

    // Skip song
    socket.on('skip', () => {
        clearInterval(playbackInterval);
        playNextSong();
    });

    // Seek to a specific position
    socket.on('seek', (position) => {
        if (currentSong && position >= 0 && position <= duration) {
            currentPosition = position;
            io.emit('progress', { currentPosition });
        }
    });

    // Remove a song from the queue
    socket.on('removeFromQueue', (index) => {
        if (index >= 0 && index < queue.length) {
            queue.splice(index, 1);
            io.emit('queueUpdated', { queue, priorityQueue });
        }
    });

    socket.on('disconnect', () => {
        console.log('A user disconnected');
    });
});

// Start the server
const PORT = 3000;
server.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
