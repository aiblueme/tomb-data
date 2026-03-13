FROM python:3.12-slim

# Build args for binary versions
ARG PAGEFIND_VERSION=1.1.0
ARG SUPERCRONIC_VERSION=0.2.29
ARG TARGETARCH=amd64

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Download pagefind binary
RUN set -eux; \
    ARCH="${TARGETARCH:-amd64}"; \
    if [ "$ARCH" = "amd64" ]; then PF_ARCH="x86_64-unknown-linux-musl"; \
    elif [ "$ARCH" = "arm64" ]; then PF_ARCH="aarch64-unknown-linux-musl"; \
    else PF_ARCH="x86_64-unknown-linux-musl"; fi; \
    curl -fsSL "https://github.com/CloudCannon/pagefind/releases/download/v${PAGEFIND_VERSION}/pagefind-v${PAGEFIND_VERSION}-${PF_ARCH}.tar.gz" \
      -o /tmp/pagefind.tar.gz \
    && tar -xzf /tmp/pagefind.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/pagefind \
    && rm /tmp/pagefind.tar.gz \
    && pagefind --version

# Download supercronic binary
RUN set -eux; \
    ARCH="${TARGETARCH:-amd64}"; \
    if [ "$ARCH" = "amd64" ]; then SC_ARCH="linux-amd64"; \
    elif [ "$ARCH" = "arm64" ]; then SC_ARCH="linux-arm64"; \
    else SC_ARCH="linux-amd64"; fi; \
    curl -fsSL "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-${SC_ARCH}" \
      -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App files
COPY build.py chart_templates.py photos.py ./
COPY templates/ ./templates/

# Crontab
RUN echo '*/5 * * * * python /app/build.py --once >> /var/log/pipeline.log 2>&1' > /etc/crontab.pipeline

# Log file
RUN touch /var/log/pipeline.log

CMD ["supercronic", "/etc/crontab.pipeline"]
