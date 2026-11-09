"""Download a model version from its GitHub Release and verify every file against the committed checksum list.

Usage: python scripts/fetch_models.py v1 [v2 ...] [--repo ns998527-rgb/cloud-command-parser] [--dest models]
The file names and SHA-256 values come from models/<version>/model.sha256 (committed in Git); the weights themselves
are only in the Release (tag model-<version>), never in Git.
"""
import argparse
import hashlib
import os
import urllib.request
import urllib.error


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("versions", nargs="+")
    ap.add_argument("--repo", default=os.environ.get("MODEL_REPO", "ns998527-rgb/cloud-command-parser"))
    ap.add_argument("--fallback-repo", default=os.environ.get("FALLBACK_MODEL_REPO", "Abhijit26918/cloud-sms"))
    ap.add_argument("--dest", default="models")
    a = ap.parse_args()
    headers = {"User-Agent": "Mozilla/5.0"}
    for v in a.versions:
        d = os.path.join(a.dest, v)
        with open(os.path.join(d, "model.sha256"), encoding="utf-8") as f:
            entries = [line.split() for line in f if line.strip()]
        for digest, name in entries:
            path = os.path.join(d, name)
            if os.path.exists(path) and sha256(path) == digest:
                continue

            repos = [a.repo]
            if a.fallback_repo and a.fallback_repo != a.repo:
                repos.append(a.fallback_repo)

            downloaded = False
            for repo in repos:
                url = f"https://github.com/{repo}/releases/download/model-{v}/{name}"
                try:
                    print(f"downloading {name} from {repo}...", flush=True)
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as out_file:
                        out_file.write(resp.read())
                    downloaded = True
                    break
                except (urllib.error.HTTPError, urllib.error.URLError) as err:
                    if repo == a.repo and len(repos) > 1:
                        print(f"Notice: asset not found in {repo}, trying mirror...", flush=True)
                        continue
                    else:
                        print(f"Failed from {repo}: {err}", flush=True)

            if not downloaded or not os.path.exists(path):
                raise SystemExit(
                    f"failed to download {name} for model {v}. "
                    f"Ensure release tag 'model-{v}' is published."
                )

            if sha256(path) != digest:
                raise SystemExit(f"checksum mismatch for {path}")
        print(f"{v}: {len(entries)} files verified")


if __name__ == "__main__":
    main()
