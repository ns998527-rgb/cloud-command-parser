# Cloud Computing Mini Project: distilled command parser on a local Kubernetes cloud

Student: **SIVA NAGA SAI**  |  Roll number: **230103002**  |  GitHub: https://github.com/ns998527-rgb/cloud-command-parser

A small English command parser (`"set an alarm for seven thirty am tomorrow"` ->
`{"intent": "alarm_set", "date": "tomorrow", "time": "seven thirty am", "place": null}`).
The teacher (Phi-3.5-mini via Ollama) labels 3,000 commands in shards; the cleaned replies train a 70M-parameter student
(EleutherAI/pythia-70m) by sequence-level knowledge distillation; the student is served from a container on k3d (Kubernetes).

## Repository map

| Path | Content |
|---|---|
| `prompts/teacher_prompt.txt` | teacher prompt |
| `worker/` | sharded teacher worker (`worker.py`), cleaner (`clean.py`), worker image (`Dockerfile`) |
| `kaggle/label_on_kaggle.py` | runs the same worker with Ollama on Kaggle (teacher inference ran there, see report) |
| `datasets/teacher/`, `datasets/v1/` | raw teacher replies (2 shards) and cleaned `train.jsonl` + `train.sha256` |
| `training/` | `config.yaml`, `train.py`, `predict.py`, `loss.csv` (v1), `loss_v2.csv` |
| `service/`, `Dockerfile` | FastAPI inference service and its image (no weights inside) |
| `cluster/k3d.yaml`, `k8s/` | cluster config and manifests (namespaces `data`, `pipeline`, `app`) |
| `network/` | `subnets.md`, `nacl.json` |
| `tests/`, `.github/workflows/ci.yml` | unit tests and CI (lint, tests, evaluation from the Release, quality gate, gitleaks) |
| `results/` | every log, score report, Locust output and command output used in the report |
| `report/report.pdf`, `AI_USE.md` | report and AI-use statement |

Model files are **not** in Git. They are GitHub Release assets: tags `model-v1` and `model-v2`
(`models/<v>/model.sha256` in Git lists the SHA-256 of every file).

## Requirements
Docker (4+ GB free for the cluster), `k3d` 5.x, `kubectl`, `make`, Python 3.10+ with `pip install boto3`.
Training additionally needs `pip install -r training/requirements.txt` (CPU only).

## Build and deploy (three commands from a fresh clone)
```
git clone https://github.com/ns998527-rgb/cloud-command-parser.git && cd cloud-command-parser
pip install boto3
make up
```
(Measured on a fresh clone: 18 min 55 s, including model downloads and image builds. On Windows run it from Git Bash and, if `python3` is not found, set `PYTHON` to an interpreter that has `boto3`, e.g. `PYTHON=python make up`.)

`make up` creates the k3d cluster, generates the S3 Secret at deploy time, starts SeaweedFS (namespace `data`), creates the
buckets `datasets` and `models` and uploads the data and the two models (downloaded from the GitHub Release and
checksum-verified), builds the images, and deploys the service (namespace `app`) behind Traefik on `http://localhost:8080`.

```
curl -s -X POST localhost:8080/parse -H "Content-Type: application/json" -d '{"text":"what is the weather in london"}'
```

## Test
```
make test                                    # unit tests
make train SUBSET=50                         # training smoke test (first 50 records)
python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest
```

## Reproduce the data and models
```
python worker/clean.py --shards datasets/teacher --out datasets/v1 --counts results/clean_counts.json   # train.jsonl + train.sha256
make train                                                          # models/v1, training/loss.csv
python training/train.py --version v2 --seed 7 --epochs 6           # models/v2, training/loss_v2.csv
make eval-local MODEL=models/v1 NAME=student_v1                     # score on validation.jsonl
```
In-cluster teacher demo: start Ollama with `phi3.5` on the laptop (`OLLAMA_HOST=0.0.0.0`), then `kubectl apply -f k8s/pipeline/teacher-workers.yaml` (two workers with `SHARD_INDEX` 0 and 1, `LIMIT=5` each; output in `datasets/teacher-incluster/`).

## Shut down
```
make down      # deletes the k3d cluster, all namespaces, Secrets and the object-store volume
```
