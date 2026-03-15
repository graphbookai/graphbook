# CUDA 12.0.1
# Ubuntu 22.04
# Nodejs 22
# Python ^3.10.12
FROM nvcr.io/nvidia/cuda:12.0.1-runtime-ubuntu22.04 AS builder

# Install system dependencies
RUN apt update -y
RUN apt install -y \
    curl \
    wget \
    make \
    python3
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash
RUN apt install -y nodejs

# Setup python and uv
RUN ln -s /usr/bin/python3.10 /usr/bin/python
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH=$PATH:/root/.cargo/bin

# Setup app
WORKDIR /app
ENV \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=60
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --frozen && rm -rf /root/.cache/uv
COPY Makefile .
COPY web web
RUN make web


FROM nvcr.io/nvidia/cuda:12.0.1-runtime-ubuntu22.04

WORKDIR /app

# Install Python and dependencies
RUN apt update -y
RUN apt-get install python3 -y
RUN ln -s /usr/bin/python3.10 /usr/bin/python
ENV PKG_PATH=/usr/local/lib/python3.10/dist-packages
COPY --from=builder $PKG_PATH $PKG_PATH

# Build app
COPY . .
COPY --from=builder /app/web/dist web/dist

EXPOSE 8005 8006

CMD ["python", "graphbook/core/cli.py", "--web_dir", "web/dist"]
