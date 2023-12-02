# MusicGen Streaming Server and Client

Turning Meta's MusicGen AI model into a live music stream.

## Usage

Requirements: `curl` and  `ffplay` (from `ffmpeg`).

Docker

```bash
bash start.sh
# And once that shows the "Listening on 8765" message, open a new terminal and run the client.
python musicgen-client.py http://localhost:8765/generate prompts.json
```

Without Docker

```bash
conda create -y --name musicgen-stream python==3.10
conda activate musicgen-stream
pip install torch transformers aiohttp_cors
python app/musicgen-server.py
# In another terminal
python musicgen-client.py http://localhost:8765/generate prompts.json
```

Music should start playing after around 10 minutes of buffering.

Hardware: 24GB VRAM for musicgen-large, 8GB is ok for small. RTX 3090 can generate three interleaved streams faster than real-time. The small model can do real-time generation even without batching, so that's your best bet for making a low-latency stream.

At real-time speed, it'll take batch size * 3 minutes to buffer the stream, so keep that in mind (or change play_stream_time to a smaller value in musicgen-client.py)

CPU generation at real-time with the small model might be possible, especially if you tune the `1 * 63616` line smaller in [https://github.com/kig/musicgen-stream/blob/f4c58e4cd89784f1e399cc89ea003079ae94ee4e/app/musicgen-server.py#L73](app/musicgen-server.py). Mac MPS produces garbled output and tends to OOM after a few iterations.

Edit the `start.sh` script to set where to save the models (huggingface cache), and you can set CUDA_VISIBLE_DEVICES, Docker network to use, etc. 

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
