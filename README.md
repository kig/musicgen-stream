# MusicGen Streaming Server and Client

Turning Meta's MusicGen AI model into a live music stream.

## Usage

Requirements: Docker, `curl` and  `ffplay` (from `ffmpeg`).
```
bash start.sh
# And once that shows the "Listening on 8765" message, open a new terminal and run the client.
python musicgen-client.py http://localhost:8765/generate prompts.json
```

Music should start playing after around 10 minutes of buffering.

Hardware: 24GB VRAM for musicgen-large, 8GB is ok for small. RTX 3090 can generate three interleaved streams faster than realtime. The small model can do real-time generation even without batching, so that's your best bet for making a low-latency stream. A M2 Macbook Air can do faster than realtime with the small model and batch size 8 (number of prompts in prompts.json).

You probably want to be on Linux, but let me know how it goes. Edit the `start.sh` script to set where to save the models (huggingface cache), and you can set CUDA_VISIBLE_DEVICES, Docker network to use, etc. 

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
