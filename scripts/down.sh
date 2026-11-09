#!/usr/bin/env bash
# Delete the cluster (and with it every namespace, Secret and the object-store volume). Run via `make down`.
set -euo pipefail
k3d cluster delete cloud-command-parser
