FROM python:3.13-slim

WORKDIR /app

# uv のインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依存ファイルを先にコピーしてキャッシュを活用
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

# ソースコードをコピー
COPY . .

ENV PORT=8096

# $HOME/eliza-memory/ を /app/.memory にマウントして使う
# docker run -v $HOME/eliza-memory:/app/.memory ...
VOLUME ["/app/.memory"]

EXPOSE 8096

CMD uv run uvicorn server:app --host 0.0.0.0 --port ${PORT} --workers 4
