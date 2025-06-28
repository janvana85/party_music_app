priority_queue = []
main_queue = []
current_song = None

def get_queues():
    return {
        "queue": main_queue,
        "priority": priority_queue
    }

def add_to_queue(song):
    main_queue.append(song)

def boost_song(song):
    priority_queue.append(song)

def get_next_song():
    global current_song
    if priority_queue:
        current_song = priority_queue.pop(0)
        return current_song
    if main_queue:
        current_song = main_queue.pop(0)
        return current_song
    current_song = None
    return None

def get_current_song():
    return current_song
