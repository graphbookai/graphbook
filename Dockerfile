# CUDA 12.0.1
# Ubuntu 22.04
# Python 3.11
# Nodejs 22
FROM nvcr.io/nvidia/cuda:12.0.1-runtime-ubuntu22.04
ARG DEADSNAKES_PPA_KEY="F23C5A6CF475977595C89F51BA6932366A755776"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Setup apt sources (nodejs and python)
RUN echo " \
deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main \
deb-src https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main" >> /etc/apt/sources.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys $DEADSNAKES_PPA_KEY

# Install system dependencies
RUN apt update -y
RUN apt install -y \
    curl \
    wget \
    make \
    python3.11
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash
RUN apt install -y nodejs

# Setup python and poetry
RUN ln -s /usr/bin/python3.11 /usr/bin/python
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python
RUN curl -sSL https://install.python-poetry.org | python
ENV PATH=$PATH:/root/.local/bin

# Setup app
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-directory
COPY . .
RUN make web

EXPOSE 8005 8006 8007

CMD ["python", "graphbook/server.py", "--web", "--web_dir", "web/dist"]
