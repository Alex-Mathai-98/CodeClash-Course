FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY codeclash/arenas/tictactoe/runtime/ /workspace/

RUN git init \
    && git config user.email "arena@codeclash.com" \
    && git config user.name "CodeClash Arena" \
    && git add . \
    && git commit -m "Initialize TicTacToe runtime" \
    && git clone --bare /workspace /opt/tictactoe-origin.git \
    && git remote add origin /opt/tictactoe-origin.git
