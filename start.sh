#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
APP_DIR="$(dirname "$SCRIPT_DIR")"/app
CACHE_DIR="$HOME/.cache"

if [ -n "$(docker images -q musicgen-stream)" ]
then 
    bash "$SCRIPT_DIR"/build.sh
fi

docker run -it --rm \
    --gpus=all \
    --name "$APP_NAME" \
    -p 8765:8765 \
    -v "$APP_DIR":/app \
    -v "$CACHE_DIR":/root/.cache \
    -v "$CACHE_DIR"/huggingface/:/root/.cache/huggingface \
    -e MODEL_NAME="$1"
    musicgen-stream
