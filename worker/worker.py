"""Sharded teacher-labelling worker (Task 1).

Reads every line of the command pool whose 0-based line number % SHARD_COUNT == SHARD_INDEX,
sends each command to the teacher (Ollama, phi3.5, temperature 0, seed 42) and writes
{"id", "text", "teacher_raw"} lines, with the teacher reply stored exactly as generated.

Environment variables
  SHARD_INDEX, SHARD_COUNT   shard selection (required)
  INPUT        pool file, local path or s3://datasets/commands_pool.jsonl
  OUTPUT_DIR   where shard-N.jsonl is written, local dir or s3://datasets/teacher
  PROMPT_FILE  prompt template containing {command} (default prompts/teacher_prompt.txt)
  OLLAMA_URL   default http://localhost:11434
  OLLAMA_MODEL default phi3.5
  LIMIT        optional: only label the first LIMIT commands of this shard (smoke tests)
  S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY   only for s3:// paths
Progress is flushed every FLUSH_EVERY (default 25) records, and a restarted worker resumes.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storage  # noqa: E402

SEED = 42
TEMPERATURE = 0
NUM_PREDICT = 120


def teacher_reply(prompt_template, command, url, model):
    prompt = prompt_template.replace("{command}", command)
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": TEMPERATURE, "seed": SEED, "num_predict": NUM_PREDICT},
    }).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["response"]


def select_shard(lines, index, count):
    return [json.loads(line) for n, line in enumerate(lines) if n % count == index]


def main():
    index, count = int(os.environ["SHARD_INDEX"]), int(os.environ["SHARD_COUNT"])
    src = os.environ.get("INPUT", "data/commands_pool.jsonl")
    out_dir = os.environ.get("OUTPUT_DIR", "datasets/teacher").rstrip("/")
    out = f"{out_dir}/shard-{index}.jsonl"
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "phi3.5")
    flush_every = int(os.environ.get("FLUSH_EVERY", "25"))
    with open(os.environ.get("PROMPT_FILE", "prompts/teacher_prompt.txt"), encoding="utf-8") as f:
        template = f.read()

    lines = [ln for ln in storage.read_text(src).splitlines() if ln.strip()]
    mine = select_shard(lines, index, count)
    if os.environ.get("LIMIT"):
        mine = mine[:int(os.environ["LIMIT"])]

    done = []
    try:  # resume
        done = [json.loads(ln) for ln in storage.read_text(out).splitlines() if ln.strip()]
    except Exception:
        pass
    seen = {d["id"] for d in done}
    print(f"shard {index}/{count}: {len(mine)} commands, {len(done)} already done", flush=True)

    def flush():
        storage.write_text(out, "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in done))

    t0, n_new = time.time(), 0
    for rec in mine:
        if rec["id"] in seen:
            continue
        raw = teacher_reply(template, rec["text"], url, model)
        done.append({"id": rec["id"], "text": rec["text"], "teacher_raw": raw})
        n_new += 1
        if n_new % flush_every == 0:
            flush()
            print(f"  {len(done)}/{len(mine)} ({(time.time() - t0) / n_new:.1f}s/cmd)", flush=True)
    flush()
    print(f"shard {index} finished: {len(done)} records -> {out}", flush=True)


if __name__ == "__main__":
    main()
