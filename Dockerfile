# CUDA 12.0.1
# Ubuntu 22.04
# Python 3.11
# Nodejs 22
FROM nvcr.io/nvidia/cuda:12.0.1-runtime-ubuntu22.04
ARG DEADSNAKES_PPA_KEY="F23C5A6CF475977595C89F51BA6932366A755776"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN echo " \
deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main \
deb-src https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main" >> /etc/apt/sources.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys $DEADSNAKES_PPA_KEY

RUN apt update -y
RUN apt install -y \
    curl \
    wget \
    make \
    python3.11

RUN ln -s /usr/bin/python3.11 /usr/bin/python
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash
RUN apt install -y nodejs

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN make web

EXPOSE 8005 8006 8007

CMD ["python", "src/server.py", "--web", "--web_dir", "web/dist"]
