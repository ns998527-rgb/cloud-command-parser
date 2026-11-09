PYTHON ?= python
SUBSET ?=

.PHONY: train test lint eval-local up down

# Fine-tune the student. Reads only training/config.yaml.
#   make train             full run (first 1500 records of datasets/v1/train.jsonl) -> models/v1, training/loss.csv
#   make train SUBSET=50   smoke test on the first 50 records only -> models/_subset
train:
	$(PYTHON) training/train.py $(if $(SUBSET),--subset $(SUBSET),)

test:
	$(PYTHON) -m pytest -q tests

lint:
	$(PYTHON) -m ruff check .

# Score a local model directory on the validation set: make eval-local MODEL=models/v1 NAME=student_v1
eval-local:
	$(PYTHON) training/predict.py --model $(MODEL) --out results/$(NAME)_predictions.jsonl
	$(PYTHON) tools/score.py results/$(NAME)_predictions.jsonl data/validation.jsonl --out results/$(NAME).json

# Build and deploy everything on a local k3d cluster / delete it again.
up:
	bash scripts/up.sh

down:
	bash scripts/down.sh
