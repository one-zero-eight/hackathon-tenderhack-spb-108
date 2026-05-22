###########################################################
# Builder stage. Build dependencies.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Install build dependencies for compiling native extensions (maybe needed only for apple silicon)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


###########################################################
# Production stage. Copy only runtime deps that were installed in the Builder stage.
FROM python:3.14-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1

# Chromium runtime deps for cloakbrowser (https://github.com/CloakHQ/CloakBrowser/blob/main/Dockerfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation \
    fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    && rm -rf /var/lib/apt/lists/*

# Copy the application from the builder
COPY --from=builder /app /app

# Create user with the name uv
RUN groupadd -g 1500 uv && \
    useradd -m -u 1500 -g uv uv

WORKDIR /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=uv:uv . /app

# Pre-download stealth Chromium at build time (not on first API request)
RUN su uv -s /bin/sh -c 'PATH="/app/.venv/bin:$PATH" cloakbrowser install && rm -f /home/uv/.cloakbrowser/.welcome_shown'

USER uv

EXPOSE 8000
CMD ["gunicorn", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "1", \
    "src.api.app:app", \
    "--timeout", "300", \
    "--forwarded-allow-ips=*" \
]
