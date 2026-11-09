# AI use

The project brief allows AI tools. This file says which one I used, for what, and how I checked the result.

## AI tool used: Claude only

I used Claude (through Claude Code in VS Code) as my coding assistant. It helped with:

- reading the assignment handout and planning the order of the work;
- drafting and debugging code: the teacher worker and `clean.py`, the training script, the FastAPI service, the Dockerfiles,
  the Kubernetes manifests, the experiment scripts, the Makefile and the GitHub Actions workflow;
- explaining ideas (sequence-level versus logit-based distillation, how a stateless NACL works, how the HPA computes load);
- drafting the report text, `README.md`, and an outline for my handwritten reflection, from the results of my own runs.

## How I checked what it gave me

- I ran the code myself on my laptop and on Kaggle and read the output; several first versions were wrong and I fixed them
  (for example the Ollama install failing on Kaggle, a training job that was killed when its shell closed, SeaweedFS crashing on a
  wrong flag, and health probes killing pods on my starved laptop).
- Unit tests (`make test`), the kit's `score.py` and `nacl_sim.py`, and a recomputation of the subnet table with Python's `ipaddress`.
- Every number in the report was copied from a file in `results/` that a real run produced. A first load-test run that failed
  (14,071 of 14,328 requests) is kept in `results/attempt1_*` and reported, not hidden.
- I tested `make down` and a fresh `git clone` followed by `make up`.

## What was not AI-made

The teacher is Phi-3.5-mini through Ollama, as the brief requires (temperature 0, seed 42). Its replies were stored exactly as
generated and never edited. No labels were written by hand or by any other model, and no validation data was used for training.
