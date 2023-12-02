import os
import sys
import struct
import subprocess
import threading
import time
import json
import math

def main():
    url = sys.argv[1]
    music_json = sys.argv[2]
    with open(music_json, "rb") as f:
        music_config = json.loads(f.read())

    stream_count = len(music_config["prompts"])
    print(music_config)

    curl = subprocess.Popen(["curl", "-s", "-k", "-N", "-q", "-d", f"@{music_json}", url], stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Play each stream for 3 minutes.
        play_stream_time = 180

        idx = 0

        bufs = [[] for i in range(stream_count)]

        pipe = None
        running = True

        while running:
            len_bytes = None
            t0 = time.time()
            for i in range(stream_count):
                len_bytes = curl.stdout.read(4)
                if not len_bytes:
                    running = False
                    break
                length = struct.unpack("<I", len_bytes)[0]
                bufs[i].append(curl.stdout.read(length))

            if not running:
                break

            elapsed = time.time() - t0
            play_time = len(bufs[0][0]) / 4 / 32000
            print(f"Buffering {idx+1} / {math.ceil(play_stream_time/play_time)}: {elapsed:.2f} s to generate, play time {len(bufs)} * {play_time:.2f} s, {(len(bufs)*play_time) / elapsed:.2f}x real-time")

            idx += 1
            if idx >= math.ceil(play_stream_time/play_time):
                idx = 0
                # create a new pipe, write all bufs to it
                buf_bytes = b''.join([b''.join(b) for b in bufs])
                bufs = [[] for i in range(stream_count)]
                if pipe is not None:
                    pipe.join()
                pipe = threading.Thread(target=subprocess.run, args=[["ffplay", "-nodisp", "-autoexit", "-hide_banner", "-f", "f32le", "-ar", "32000", "-ac", "1", "-i", "-"]], kwargs=dict(input=buf_bytes))
                pipe.start()

        if pipe is not None:
            pipe.join()
    finally:
        curl.terminate()

if __name__ == "__main__":
    main()
