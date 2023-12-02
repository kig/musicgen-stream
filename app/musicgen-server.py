import numpy as np

import aiohttp
from aiohttp import web, WSCloseCode
import aiohttp_cors
import asyncio

import time
import json

from transformers import AutoProcessor, MusicgenForConditionalGeneration
import torch

device = 'cpu'
if torch.cuda.is_available():
    device = 'cuda'
elif torch.backends.mps.is_available():
    device = 'mps'

model_name = "facebook/musicgen-small"
processor = AutoProcessor.from_pretrained(model_name)
model = torch.compile(MusicgenForConditionalGeneration.from_pretrained(model_name)).to(device)

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
        for p, i in enumerate(prompts):
            if len(new_prompts) > i:
                prompts[i] = new_prompts[i]

def run_generate():
    sampling_rate = model.config.audio_encoder.sampling_rate
    audio_values = None

    while True:
        tokens = 100

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

        print(time.time(), new_audio_values.shape, sampling_rate, tokens)
        start = 0
        if audio_values is not None:
            start = audio_values[0].shape[0]

        for i in range(len(prompts)):
            yield new_audio_values[i][0][start:].tobytes()

        max_len = 1 * 63616
        cut_start = 0
        if audio_values is not None:
            cut_start = max(0, audio_values[0].shape[0] - max_len)
        audio_values = [new_audio_values[i][0][cut_start:] for i in range(len(prompts))]

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

    set_prompts(cmd['prompts'], init=True)

    audio_bufs = run_generate()
    for audio_bytes in audio_bufs:
        length = audio_bytes.__len__().to_bytes(4, 'little')
        await resp.write(length)
        await resp.write(audio_bytes)
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

    set_prompts(cmd['prompts'])
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
    print(f"Server running on {host}:{port}")
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="MusicGen Server", description="Runs a HTTP POST server that generates music using MusicGen")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    start_server(args.host, args.port)
