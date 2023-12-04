# MusicGen Streaming Server and Client

Turning Meta's MusicGen AI model into a live music stream.

## Usage

Requirements: `curl` and  `ffplay` (from `ffmpeg`).

Docker

```bash
bash start.sh facebook/musicgen-small
# Once that shows the "Listening on 8765" message, open a new terminal and run the client.
python musicgen-client.py
```

Without Docker

```bash
conda create -y --name musicgen-stream python==3.10
conda activate musicgen-stream
pip install torch transformers aiohttp_cors
python app/musicgen-server.py --model facebook/musicgen-small --dtype float16
# In another terminal
python musicgen-client.py --server http://localhost:8765/generate --prompts prompts.json
```

Music should start playing after around 10 minutes of buffering.

Change prompts of the running stream. Note that the number of prompts is capped to the number of prompts running on the server. This takes quite long to register on the server side.

```bash
curl -k -d @new_prompts.json http://localhost:8765/set_prompts
```

Hardware: 24GB VRAM for musicgen-large, 8GB is ok for small. RTX 3090 can generate three interleaved streams faster than real-time. The small model can do real-time generation even without batching, so that's your best bet for making a low-latency stream.

At real-time speed, it'll take batch size * 3 minutes to buffer the stream, so keep that in mind (or change play_stream_time to a smaller value in musicgen-client.py)

CPU generation at real-time with the small model might be possible, haven't succeeded though. Mac MPS produces garbled output and tends to OOM after a few iterations.

When running with Docker, edit the `start.sh` script to set which model to use, where to save the models (huggingface cache), and you can set CUDA_VISIBLE_DEVICES, Docker network to use, etc. 

## HTTPS?

You can run this with a Caddy reverse proxy in front.

Caddyfile snippet

```
    handle_path /_/musicgen-stream/* {
        header {
            Access-Control-Allow-Origin "*"
            Access-Control-Expose-Headers *
            defer
        }
        reverse_proxy http://musicgen-stream:8765
    }
```

Then start Caddy with:

```bash
docker run -it --rm -p 80:80 -p 443:443 \
    --name caddy \
    -v /www/caddy/Caddyfile:/etc/caddy/Caddyfile \
    -v /www/caddy/data:/data \
    -v /www/html:/html \
    caddy
```

With that, you can access the musicgen stream at https://localhost/_/musicgen-stream/generate
