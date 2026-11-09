"""Clean the teacher shards into the training set (Task 1, step 6).

Usage
  python worker/clean.py --shards SHARD_DIR_OR_S3_PREFIX --out OUT_DIR_OR_S3_PREFIX [--counts results/clean_counts.json]

Reads every shard-*.jsonl, orders records by id and rejects, checking in this order:
  (a) reply is not valid JSON
  (b) keys are not exactly intent, date, time, place (a valid non-object also lands here)
  (c) intent is not one of the eight
  (d) a slot is neither null nor text that appears in the command
then (e) duplicate commands (the record with the smallest id is kept).
Every rejected record is counted once, under the first reason that applies, so
input = a + b + c + d + duplicates + kept.
Writes train.jsonl (LF line endings, UTF-8, id order) and train.sha256 ("<hex>  train.jsonl").
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storage  # noqa: E402

KEYS = {"intent", "date", "time", "place"}
INTENTS = {"alarm_set", "alarm_query", "calendar_set", "calendar_query", "calendar_remove",
           "weather_query", "datetime_query", "recommendation_events"}


def classify(rec):
    """Return None if the record is good, else 'a', 'b', 'c' or 'd'."""
    try:
        obj = json.loads(rec["teacher_raw"])
    except (json.JSONDecodeError, TypeError):
        return "a"
    if not isinstance(obj, dict) or set(obj) != KEYS:
        return "b"
    if not isinstance(obj["intent"], str) or obj["intent"] not in INTENTS:
        return "c"
    text = rec["text"].lower()
    for k in ("date", "time", "place"):
        v = obj[k]
        if v is None:
            continue
        if not isinstance(v, str) or not v.strip() or v.lower() not in text:
            return "d"
    return None


def clean(records):
    records = sorted(records, key=lambda r: r["id"])
    counts = {"input": len(records), "a_invalid_json": 0, "b_wrong_keys": 0,
              "c_bad_intent": 0, "d_slot_not_in_command": 0, "duplicates": 0, "kept": 0}
    names = {"a": "a_invalid_json", "b": "b_wrong_keys", "c": "c_bad_intent", "d": "d_slot_not_in_command"}
    kept, seen = [], set()
    for r in records:
        bad = classify(r)
        if bad:
            counts[names[bad]] += 1
        elif r["text"] in seen:
            counts["duplicates"] += 1
        else:
            seen.add(r["text"])
            kept.append(r)
    counts["kept"] = len(kept)
    assert counts["input"] == sum(v for k, v in counts.items() if k != "input")
    return kept, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shards", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", help="write the counts as JSON here")
    a = ap.parse_args()

    records = []
    for uri in storage.list_keys(a.shards):
        if os.path.basename(uri).startswith("shard-") and uri.endswith(".jsonl"):
            records += [json.loads(ln) for ln in storage.read_text(uri).splitlines() if ln.strip()]
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        sys.exit("a command id appears more than once across shards")
    kept, counts = clean(records)

    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    out = a.out.rstrip("/")
    storage.write_bytes(f"{out}/train.jsonl", data)
    storage.write_text(f"{out}/train.sha256", f"{digest}  train.jsonl\n")
    counts["sha256"] = digest
    print(json.dumps(counts, indent=2))
    if a.counts:
        os.makedirs(os.path.dirname(a.counts) or ".", exist_ok=True)
        with open(a.counts, "w", encoding="utf-8", newline="\n") as f:
            json.dump(counts, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
