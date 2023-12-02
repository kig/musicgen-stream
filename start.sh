#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
APP_DIR="$SCRIPT_DIR"/app
CACHE_DIR="$HOME/.cache"

if [ -z "$(docker images -q musicgen-stream)" ]
then
    bash "$SCRIPT_DIR"/build.sh
fi

model=$1

if [ -z "$model" ]
then
    model="facebook/musicgen-small"
fi

docker run -it --rm \
    --name "$APP_NAME" \
    -p 8765:8765 \
    -v "$APP_DIR":/app \
    -v "$CACHE_DIR":/root/.cache \
    -v "$CACHE_DIR"/huggingface/:/root/.cache/huggingface \
    -e MODEL_NAME="$model" \
    musicgen-stream
