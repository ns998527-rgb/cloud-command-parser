"""Run a model (local dir or Hugging Face name) over validation commands and write score.py predictions.

Usage: python training/predict.py --model models/v1 --data data/validation.jsonl --out results/student_v1_predictions.jsonl
Uses the same prompt and greedy decoding as the service. The raw first output line is stored as the prediction.
"""
import argparse
import json
import sys
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", default="data/validation.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=64)
    a = ap.parse_args()

    torch.set_num_threads(os.cpu_count() or 1)
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float32).eval()
    with open(a.data, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as out:
        for i, r in enumerate(rows, 1):
            ids = tok(f"Command: {r['text']}\nJSON:", return_tensors="pt")
            with torch.no_grad():
                g = model.generate(**ids, max_new_tokens=a.max_new_tokens, do_sample=False,
                                   pad_token_id=tok.eos_token_id, eos_token_id=tok.eos_token_id)
            text = tok.decode(g[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
            pred = text.strip().split("\n", 1)[0].strip()
            out.write(json.dumps({"id": r["id"], "prediction": pred}, ensure_ascii=False) + "\n")
            if i % 20 == 0:
                print(f"{i}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
