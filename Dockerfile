# Inference service image. No model weights inside: they are downloaded from object storage at start-up.
# Build:  docker build -t command-parser:1.0 .
FROM python:3.11.10-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# CPU-only PyTorch (the default wheels pull in GPU libraries we do not need)
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1+cpu
COPY service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY data/schema.json /app/schema.json
COPY service/app.py service/validation.py /app/

ENV SCHEMA_PATH=/app/schema.json MODEL_DIR=/tmp/model
EXPOSE 8000
USER 1000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
