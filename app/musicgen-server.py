import time

t00 = time.time()

print(f"{time.time():.2f}: Loading modules")
t0 = time.time()

from aiohttp import web
import aiohttp_cors
import asyncio

import numpy as np
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import torch

print(f"{time.time():.2f}: Loaded modules in {time.time()-t0:.2f} s")

device = 'cpu'
if torch.cuda.is_available():
    device = 'cuda'
# MPS runs out of memory and produces garbled output
#elif torch.backends.mps.is_available():
#    device = 'mps'

model_name = None
model = None
processor = None

prompts = []

def get_prompts():
    global prompts
    return prompts

def set_prompts(new_prompts, init=False):
    global prompts
    if init:
        prompts.clear()
        for p in new_prompts:
            prompts.append(p)
    else:
        for i in range(min(len(prompts), len(new_prompts))):
            prompts[i] = new_prompts[i]

def run_generate():
    sampling_rate = model.config.audio_encoder.sampling_rate
    audio_values = None

    while True and len(prompts) > 0:
        tokens = 100

        t0 = time.time()

        inputs = processor(
          audio=audio_values,
          text=prompts,
          padding=True,
          sampling_rate=sampling_rate,
          return_tensors="pt"
        ).to(model.device)

        if audio_values is not None:
            inputs["input_values"] = inputs["input_values"].to(model.dtype)

        new_audio_values = model.generate(**inputs, max_new_tokens=tokens).to(torch.float).to('cpu').numpy()

        start = 0
        if audio_values is not None:
            start = audio_values[0].shape[0]

        new_audio_samples = sum([len(new_audio_values[i][0][start:]) for i in range(len(prompts))])
        elapsed = time.time() - t0
        realtime_fraction = (new_audio_samples / sampling_rate) / elapsed

        print(f"Generated {new_audio_samples / sampling_rate:.2f} s of audio in {elapsed:.2f} s, {realtime_fraction:.2f}x real-time")

        print(f"{time.time():.2f}: {new_audio_values.shape} @ {sampling_rate} Hz, {tokens} tokens")

        for i in range(len(prompts)):
            yield new_audio_values[i][0][start:].tobytes()

        max_len = 4 * 32000 # 4 seconds. 500 tokens is 318080 samples.
        cut_start = 0
        if audio_values is not None:
            cut_start = max(0, audio_values[0].shape[0] - max_len)
        audio_values = [new_audio_values[i][0][cut_start:] for i in range(len(prompts))]
        # # trim silence in the beginning
        # # if the silence is longer than 64000 samples, or 2 seconds, cut it
        # # silence is audio values abs(v) < 0.01
        # for i in range(len(audio_values)):
        #     # take the average of the first 64000 samples in audio_values[i]
        #     #avg = torch.mean(torch.abs(audio_values[i][:64000]))
        #     # audio_values[i] is a numpy array, so we can't use torch.mean
        #     avg = abs(audio_values[i][:64000]).mean()
        #     if avg < 0.05:
        #         # search for the end of the silence
        #         # do this in one second chunks
        #         j = 64000
        #         while j < audio_values[i].shape[0]:
        #             #avg = torch.mean(torch.abs(audio_values[i][j:j+8000]))
        #             avg = abs(audio_values[i][j:j+8000]).mean()
        #             if avg > 0.05:
        #                 break
        #             j += 8000
        #         audio_values[i] = audio_values[i][j:]
                    

async def http_handler_generate(request):
    peername = request.transport.get_extra_info('peername')
    if peername is not None:
        host, port = peername
    request_addr = f"{host}:{port}"
    if 'X-Forwarded-For' in request.headers:
        request_addr += f" ({request.headers['X-Forwarded-For']})"
    print(f"Generate request: {request_addr}")
    cmd = await request.json()
    resp = web.StreamResponse()
    resp.content_type = 'application/octet-stream'
    await resp.prepare(request)

    if "mp3" in cmd and cmd["mp3"]:
        import lameenc
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(96)
        encoder.set_in_sample_rate(32000)
        encoder.set_channels(1)
        encoder.set_quality(2)
        encoder.silence()

    set_prompts(cmd['prompts'], init=True)

    # Buffer the output bufs for 3 minutes if mp3 is requested
    # Encode the 3 minute bufs to mp3 using lame and send it to the client
    # Repeat for as long as the client is connected
    # If mp3 is not requested, send the raw audio bytes to the client without buffering.
    audio_bufs = run_generate()
    output_bufs = [[] for i in range(len(prompts))]
    output_idx = 0
    buffer_seconds = 180
    if "buffer_seconds" in cmd:
        buffer_seconds = cmd["buffer_seconds"]
    for audio_bytes in audio_bufs:
        if "mp3" in cmd and cmd["mp3"]:
            output_bufs[output_idx].append(audio_bytes)
            buffered = sum([len(b) for b in output_bufs[output_idx]]) / 4 / 32000
            print(f"Buffering {output_idx+1} / {len(prompts)}: {buffered:.2f} s / {buffer_seconds} s")
            if buffered >= buffer_seconds:
                # encode the 3 minute bufs to mp3 using lame
                buf_bytes = b''.join(output_bufs[output_idx])
                buf_bytes_s16le = (np.frombuffer(buf_bytes, dtype=np.float32) * 32767).astype(np.int16).tobytes()
                output_bufs[output_idx].clear()
                mp3_bytes = encoder.encode(buf_bytes_s16le)
                await resp.write(mp3_bytes)
            output_idx = (output_idx + 1) % len(prompts)
        else:
            length = audio_bytes.__len__().to_bytes(4, 'little')
            await resp.write(length)
            await resp.write(audio_bytes)

    if "mp3" in cmd and cmd["mp3"]:
        for output_idx in range(len(prompts)):
            # encode the remaining bufs to mp3 using lame
            buf_bytes = b''.join(output_bufs[output_idx])
            buf_bytes_s16le = (np.frombuffer(buf_bytes, dtype=np.float32) * 32767).astype(np.int16).tobytes()
            output_bufs[output_idx].clear()
            mp3_bytes = encoder.encode(buf_bytes_s16le)
            await resp.write(mp3_bytes)
        # Flush when finished encoding the entire stream
        mp3_bytes = encoder.flush()
        await resp.write(mp3_bytes)

    await resp.write_eof()

    return resp

async def http_handler_set_prompts(request):
    peername = request.transport.get_extra_info('peername')
    if peername is not None:
        host, port = peername
    request_addr = f"{host}:{port}"
    if 'X-Forwarded-For' in request.headers:
        request_addr += f" ({request.headers['X-Forwarded-For']})"
    print(f"Change prompts request: {request_addr}")
    cmd = await request.json()
    resp = web.StreamResponse()
    resp.content_type = 'text/plain'
    await resp.prepare(request)

    prompts = cmd['prompts']
    set_prompts(prompts, init=len(prompts) == 0)
    await resp.write_eof()

    return resp

def start_server(host="0.0.0.0", port=8765):
    app = web.Application()
    app.add_routes([
        web.post('/generate', http_handler_generate),
        web.post('/set_prompts', http_handler_set_prompts),
    ])
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*"
        )
    })

    for route in list(app.router.routes()):
        cors.add(route)
    print(f"{time.time():.2f}: Server running on {host}:{port}, total startup time {time.time()-t00:.2f} s")
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="MusicGen Server", description="Runs a HTTP POST server that generates music using MusicGen")
    parser.add_argument("--model", type=str, default="facebook/musicgen-small")
    parser.add_argument("--dtype", type=str, default="float")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    dtype = torch.float16
    if args.dtype == "float":
        dtype = torch.float

    print(f"{time.time():.2f}: Loading model {args.model} on {device} with dtype {dtype}")
    t0 = time.time()

    model_name = args.model
    processor = AutoProcessor.from_pretrained(model_name)
    model = torch.compile(MusicgenForConditionalGeneration.from_pretrained(model_name).to(dtype)).to(device)

    print(f"{time.time():.2f}: Loaded model in {time.time()-t0:.2f} s")

    start_server(args.host, args.port)
