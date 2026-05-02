# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the wheel from the source tree ---------------------------
FROM python:3.12-slim AS builder

WORKDIR /src
COPY pyproject.toml README.md ./
COPY scythe ./scythe

RUN python -m pip install --upgrade pip build \
    && python -m build --wheel --outdir /dist

# ---- Stage 2: minimal runtime image -----------------------------------------
FROM python:3.12-slim AS runtime

# Force UTF-8 stdio so Rich's box-drawing/braille glyphs render correctly
# regardless of the host locale (same fix as in CI).
ENV PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install just the wheel produced upstream — keeps the layer cacheable
# and the final image small (no source tree, no build tools).
COPY --from=builder /dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm -f /tmp/*.whl

# Run as a non-root user. UID 1000 matches the typical host user on Linux,
# which keeps file ownership sane when bind-mounting the user's projects.
RUN useradd --create-home --uid 1000 scythe
USER scythe

# /work is the conventional mount point. Documented in the README:
#   docker run --rm -v "$PWD":/work ghcr.io/elielmengue/scythe scan /work
WORKDIR /work

ENTRYPOINT ["scythe"]
CMD ["--help"]

# OCI metadata — populated by docker/metadata-action in CI but useful for
# people who build the image locally.
LABEL org.opencontainers.image.title="artifact-scythe" \
      org.opencontainers.image.description="Reclaim disk space by harvesting build artifacts" \
      org.opencontainers.image.source="https://github.com/elielMengue/scythe" \
      org.opencontainers.image.licenses="MIT"
