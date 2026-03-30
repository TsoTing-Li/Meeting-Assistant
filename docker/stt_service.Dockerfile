FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common ffmpeg && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3.11 -m ensurepip --upgrade

WORKDIR /app

RUN python3.11 -m pip install --no-cache-dir \
    faster-whisper \
    fastapi \
    "uvicorn[standard]" \
    python-multipart \
    pydantic \
    pydantic-settings \
    python-dotenv

COPY core/ ./core/
COPY services/stt_service/ ./services/stt_service/

EXPOSE 8080

CMD ["python3.11", "-m", "uvicorn", "services.stt_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
