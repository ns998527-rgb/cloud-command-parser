"""Turn worker output (shard files with teacher_raw) into a score.py predictions file.

Usage: python worker/to_predictions.py SHARD_FILE PREDICTIONS_FILE
"""
import json
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8", newline="\n") as out:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out.write(json.dumps({"id": r["id"], "prediction": r["teacher_raw"]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
