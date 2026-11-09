"""Command-parser inference service (Task 3).

Endpoints
  POST /parse    {"text": "..."} -> 200 four-key JSON (+ X-Model-Version, X-Served-By headers)
                 or 500 {"error": "invalid_model_output"} when the model output fails the schema
  GET  /healthz  200 while the process is alive
  GET  /readyz   503 until the model is loaded, then 200

Environment variables
  MODEL_URI        s3://models/v1/  (where the model + tokenizer live)
  MODEL_VERSION    e.g. v1, returned in X-Model-Version
  S3_ENDPOINT      object-store endpoint (SeaweedFS S3 gateway)
  MAX_NEW_TOKENS   generation limit
  FAULT_INJECT     1 -> replace the model output with "not json" before validation (testing)
Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, injected from a Kubernetes Secret.
"""
import os
import threading
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import validation

MODEL_URI = os.environ.get("MODEL_URI", "")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "unknown")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "64"))
POD_NAME = os.environ.get("HOSTNAME", "local")
MODEL_DIR = os.environ.get("MODEL_DIR", "/tmp/model")
MAX_INPUT_CHARS = 500

SCHEMA = validation.load_schema()


class State:
    model = None          # object with .generate(text) -> str ; set when loading finishes
    load_error = None
    load_seconds = None


state = State()
_gen_lock = threading.Lock()


class TorchModel:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "1")))
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float32)
        self.model.eval()

    def generate(self, text):
        prompt = f"Command: {text}\nJSON:"
        ids = self.tok(prompt, return_tensors="pt")
        with self.torch.no_grad():
            out = self.model.generate(
                **ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                pad_token_id=self.tok.eos_token_id, eos_token_id=self.tok.eos_token_id)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


def download_model(uri, dest):
    import boto3
    bucket, _, prefix = uri[len("s3://"):].partition("/")
    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT or None,
                      region_name=os.environ.get("AWS_REGION", "us-east-1"))
    os.makedirs(dest, exist_ok=True)
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(prefix):].lstrip("/")
            if not name or name.endswith("/"):
                continue
            target = os.path.join(dest, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            s3.download_file(bucket, obj["Key"], target)
            n += 1
    if n == 0:
        raise RuntimeError(f"no objects found under {uri}")
    print(f"downloaded {n} files from {uri} to {dest}", flush=True)


def load_model():
    t0 = time.time()
    try:
        print(f"loading model {MODEL_VERSION} from {MODEL_URI}", flush=True)
        download_model(MODEL_URI, MODEL_DIR)
        model = TorchModel(MODEL_DIR)
        model.generate("set an alarm for seven am")  # warm-up: the first call is several seconds slower
        state.model = model
        state.load_seconds = round(time.time() - t0, 2)
        print(f"model ready in {state.load_seconds}s", flush=True)
    except Exception as e:  # keep the process alive; /readyz stays 503
        state.load_error = repr(e)
        print(f"model load failed: {e!r}", flush=True)


app = FastAPI(title="command-parser")


@app.on_event("startup")
def _startup():
    if os.environ.get("SKIP_MODEL_LOAD") != "1":
        threading.Thread(target=load_model, daemon=True).start()


class ParseRequest(BaseModel):
    text: str


@app.get("/healthz")
def healthz():
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    if state.model is None:
        return JSONResponse({"status": "loading", "error": state.load_error}, status_code=503)
    return {"status": "ready"}


@app.post("/parse")
def parse(req: ParseRequest):
    headers = {"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME}
    if state.model is None:
        return JSONResponse({"error": "model_not_ready"}, status_code=503, headers=headers)
    text = req.text.strip()[:MAX_INPUT_CHARS]
    if os.environ.get("FAULT_INJECT") == "1":
        raw = "not json"
    else:
        with _gen_lock:
            raw = state.model.generate(text)
    obj = validation.validate_output(validation.first_json_candidate(raw), SCHEMA)
    if obj is None:
        return JSONResponse({"error": "invalid_model_output"}, status_code=500, headers=headers)
    return JSONResponse(obj, headers=headers)
