#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
APP_DIR="$SCRIPT_DIR"/app
CACHE_DIR="$HOME/.cache"
APP_NAME="$(basename "$SCRIPT_DIR")"

if [ -z "$(docker images -q musicgen-stream)" ]
then
    bash "$SCRIPT_DIR"/build.sh
fi

model=$1

if [ -z "$model" ]
then
    model="facebook/musicgen-small"
fi

GPU_ENABLED=""
if [ ! -z "$(which nvidia-smi)" ]
then
    GPU_ENABLED="--gpus=all"
    if [ ! -z "$2" ]
    then
        GPU_ENABLED="--gpus=device=$2"
    fi
fi

docker run -it --rm \
    $GPU_ENABLED \
    --name "$APP_NAME" \
    -p 8765:8765 \
    -v "$APP_DIR":/app \
    -v "$CACHE_DIR"/huggingface/:/root/.cache/huggingface \
    -e MODEL_NAME="$model" \
    musicgen-stream
