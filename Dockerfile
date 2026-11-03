# CPU-only image for the web app. No CUDA, no GPU base image.
# Build from the repository root:
#   docker build -t galion-deep-mr-fake-web .
#   docker run --rm -p 8765:8765 galion-deep-mr-fake-web

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Runtime dependencies only. Ruff/Black stay in requirements-dev.txt
# and are installed by the host scripts, not this image.
COPY web/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY web/ /app/web/

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app \
    && mkdir -p /app/web/uploads /app/web/outputs \
    && chown -R app:app /app/web

WORKDIR /app/web
USER app

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health')" || exit 1

# Bind all interfaces so the published port is reachable from the host.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8765"]
