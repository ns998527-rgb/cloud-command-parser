"""Fine-tune pythia-70m on teacher replies (sequence-level knowledge distillation), CPU only.

Each example is   "Command: <command>\\nJSON: <teacher JSON reply><eos>"
and the loss is computed on the JSON part only (the command is the input, the teacher reply is the target).

Usage
  python training/train.py                       # reads training/config.yaml, writes models/v1 + training/loss.csv
  python training/train.py --subset 50           # smoke test: first 50 records only, writes to models/_subset
  python training/train.py --version v2 --seed 7 --epochs 8     # second model version
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import random
import subprocess
import time

import numpy as np
import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_example(tok, command, reply, max_len):
    """Return (input_ids, labels) with the prompt part masked out of the loss."""
    prompt_ids = tok(f"Command: {command}\nJSON:")["input_ids"]
    full_ids = tok(f"Command: {command}\nJSON: {reply.strip()}")["input_ids"] + [tok.eos_token_id]
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return full_ids[:max_len], labels[:max_len]


def collate(batch, pad_id):
    n = max(len(x[0]) for x in batch)
    ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
    lab = torch.full((len(batch), n), -100, dtype=torch.long)
    att = torch.zeros((len(batch), n), dtype=torch.long)
    for i, (x, y) in enumerate(batch):
        ids[i, :len(x)], lab[i, :len(y)], att[i, :len(x)] = (
            torch.tensor(x), torch.tensor(y), 1)
    return ids, lab, att


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="training/config.yaml")
    ap.add_argument("--subset", type=int, help="train on the first N records only (smoke test)")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--out", help="output dir (default models/<version>)")
    ap.add_argument("--loss-csv", help="loss file (default training/loss.csv for v1, training/loss_<version>.csv otherwise)")
    a = ap.parse_args()

    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    seed = a.seed if a.seed is not None else cfg["seed"]
    epochs = a.epochs if a.epochs is not None else cfg["epochs"]
    lr = a.lr if a.lr is not None else cfg["learning_rate"]
    n_examples = a.subset if a.subset else cfg["train_examples"]
    if a.subset:
        out_dir, loss_csv = a.out or "models/_subset", a.loss_csv or "training/loss_subset.csv"
    else:
        out_dir = a.out or f"models/{a.version}"
        loss_csv = a.loss_csv or ("training/loss.csv" if a.version == "v1" else f"training/loss_{a.version}.csv")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(os.cpu_count() or 1)

    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(cfg["base_model"], torch_dtype=torch.float32)

    records = sorted(read_jsonl(cfg["train_file"]), key=lambda r: r["id"])[:n_examples]
    data = [build_example(tok, r["text"], r["teacher_raw"], cfg["max_seq_len"]) for r in records]
    print(f"training on {len(data)} examples, {epochs} epochs, lr {lr}, seed {seed}", flush=True)

    bs = cfg["batch_size"]
    steps = epochs * ((len(data) + bs - 1) // bs)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=cfg["weight_decay"])
    sched = get_linear_schedule_with_warmup(opt, int(cfg["warmup_ratio"] * steps), steps)
    gen = torch.Generator().manual_seed(seed)

    os.makedirs(os.path.dirname(loss_csv) or ".", exist_ok=True)
    rows = []
    model.train()
    t0 = time.time()
    for epoch in range(1, epochs + 1):
        order = torch.randperm(len(data), generator=gen).tolist()
        total, count = 0.0, 0
        for i in range(0, len(order), bs):
            ids, lab, att = collate([data[j] for j in order[i:i + bs]], tok.pad_token_id)
            loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total, count = total + loss.item(), count + 1
        rows.append((epoch, round(total / count, 6)))
        print(f"epoch {epoch}/{epochs} loss {rows[-1][1]} ({time.time() - t0:.0f}s)", flush=True)
        with open(loss_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["epoch", "train_loss"])
            w.writerows(rows)

    model.eval()
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    tok.save_pretrained(out_dir)

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = "unknown"
    info = {"version": a.version, "base_model": cfg["base_model"], "seed": seed, "epochs": epochs,
            "learning_rate": lr, "batch_size": bs, "max_seq_len": cfg["max_seq_len"],
            "train_examples": len(data), "final_train_loss": rows[-1][1], "git_commit": commit,
            "torch": torch.__version__, "python": platform.python_version(),
            "train_seconds": round(time.time() - t0)}
    with open(os.path.join(out_dir, "version_info.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=2)
        f.write("\n")

    files = sorted(n for n in os.listdir(out_dir) if n != "model.sha256")
    with open(os.path.join(out_dir, "model.sha256"), "w", encoding="utf-8", newline="\n") as f:
        for n in files:
            f.write(f"{sha256_file(os.path.join(out_dir, n))}  {n}\n")
    print(f"saved {out_dir}: {files}", flush=True)


if __name__ == "__main__":
    main()
