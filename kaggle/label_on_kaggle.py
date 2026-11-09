"""Run the teacher (Ollama phi3.5) on Kaggle and produce the Task 1 shards.

Why Kaggle: the teacher needs hours on a 4-thread / 7.7 GB laptop CPU. This script runs the SAME
worker (worker/worker.py), the SAME prompt (prompts/teacher_prompt.txt) and the SAME settings
(phi3.5, temperature 0, seed 42) as the cluster workers; only the hardware differs.

Use in a Kaggle notebook (Settings: Accelerator = GPU T4 x2 or P100, Internet = On).
Cell 1:   !git clone https://github.com/ns998527-rgb/cloud-command-parser.git && cd cloud-command-parser && python kaggle/label_on_kaggle.py
Then download /kaggle/working/teacher_output.zip from the notebook Output panel.
Output: shards (datasets/teacher/shard-0..N-1.jsonl) and the validation run (results/teacher_val_*).
"""
import os
import subprocess
import sys
import time
import urllib.request

SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "2"))
OUT = "/kaggle/working"
REPO = os.getcwd()


def sh(cmd, **kw):
    print("+", cmd, flush=True)
    return subprocess.run(cmd, shell=True, check=True, **kw)


def wait_ollama():
    for _ in range(120):
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            return
        except Exception:
            time.sleep(1)
    sys.exit("ollama did not start")


def install_ollama():
    """ollama.com/install.sh sometimes returns HTTP 500; retry, then use the GitHub release binary."""
    for _ in range(3):
        if subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True).returncode == 0:
            return
        time.sleep(5)
    print("install.sh failed; installing from GitHub releases", flush=True)
    base = "https://github.com/ollama/ollama/releases/latest/download"
    if subprocess.run(f"curl -fL {base}/ollama-linux-amd64.tar.zst | tar --zstd -x -C /usr/local",
                      shell=True).returncode != 0:
        sh(f"curl -fL {base}/ollama-linux-amd64.tgz | tar -xz -C /usr/local")
    sh("ollama --version")


def main():
    sh("apt-get update -qq && apt-get install -y -qq zstd curl > /dev/null")
    install_ollama()
    subprocess.Popen(["ollama", "serve"], stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
    wait_ollama()
    sh("ollama pull phi3.5")
    sh("ollama --version; ollama list")

    out_dir = os.path.join(REPO, "datasets", "teacher")
    # Shards run one after another here (one GPU); in the cluster they run as parallel pods.
    for i in range(SHARD_COUNT):
        env = dict(os.environ, SHARD_INDEX=str(i), SHARD_COUNT=str(SHARD_COUNT),
                   INPUT="data/commands_pool.jsonl", OUTPUT_DIR=out_dir)
        sh("python worker/worker.py", env=env)

    # Teacher on the validation commands (Task 2 step 6): same prompt and settings.
    os.makedirs("results", exist_ok=True)
    env = dict(os.environ, SHARD_INDEX="0", SHARD_COUNT="1", INPUT="data/validation.jsonl",
               OUTPUT_DIR=os.path.join(REPO, "results", "teacher_val_raw"))
    sh("python worker/worker.py", env=env)
    sh("python worker/to_predictions.py results/teacher_val_raw/shard-0.jsonl results/teacher_validation_predictions.jsonl")
    sh("python tools/score.py results/teacher_validation_predictions.jsonl data/validation.jsonl "
       "--out results/teacher_validation.json")

    sh("ollama --version > results/ollama_version.txt; ollama list >> results/ollama_version.txt")
    sh(f"cd {REPO} && zip -r {OUT}/teacher_output.zip datasets/teacher results/teacher_val_raw "
       "results/teacher_validation_predictions.jsonl results/teacher_validation.json results/ollama_version.txt")
    print("DONE: download", f"{OUT}/teacher_output.zip")


if __name__ == "__main__":
    main()
