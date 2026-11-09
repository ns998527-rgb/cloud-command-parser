# Teacher-labelling worker / cleaner image (no model inside: the teacher is Ollama, reached over HTTP).
# Build from the repo root:  docker build -f worker/Dockerfile -t teacher-worker:1.0 .
FROM python:3.11.10-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install boto3==1.35.70
WORKDIR /app
COPY worker/ /app/worker/
COPY prompts/teacher_prompt.txt /app/prompts/teacher_prompt.txt
CMD ["python", "worker/worker.py"]
