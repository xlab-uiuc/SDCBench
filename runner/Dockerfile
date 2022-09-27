# For more information, please refer to https://aka.ms/vscode-docker-python
#FROM python:3.8-slim
FROM ubuntu:latest
#FROM frolvlad/alpine-glibc

RUN apt-get update && apt-get install -y \
    gcc \
    g++
#    software-properties-common

#RUN add-apt-repository ppa:deadsnakes/ppa

RUN apt-get install -y \
    python3 \
    python3-pip

RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install -y \
    python3-tk

RUN apt-get upgrade -y \
    libc6 \
    libstdc++6

RUN apt-get dist-upgrade

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN python3 --version

# Install pip requirements
COPY requirements.txt .
#RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
#RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
#USER appuser

ENV SDC_TIMEOUT 300
ENV SDC_ENDPOINT http://pepega.cs.illinois.edu:5000

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["sh", "-c", "jurigged app.py --endpoint=${SDC_ENDPOINT}"]

