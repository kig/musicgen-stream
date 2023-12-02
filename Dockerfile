# Container for building the environment
FROM condaforge/mambaforge:4.9.2-5 as conda

RUN --mount=type=cache,target=/opt/conda/pkgs mamba create --copy -p /env python==3.10 && conda clean -afy
RUN --mount=type=cache,target=/root/.cache/pip conda run -p /env python -m pip install aiohttp_cors transformers numpy torch

COPY musicgen-server.py /app/
CMD conda run -p /env python /app/musicgen-server.py
