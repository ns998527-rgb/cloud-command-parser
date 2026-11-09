#!/usr/bin/env bash
# Task 4 step 2 evidence: while the model is still loading, the Service must have NO ready endpoints.
# Deletes all parser pods and, every 2 s, records the Service's READY addresses and NOT-READY addresses.
# Output: results/endpoints_while_loading.txt
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=results/endpoints_while_loading.txt
: > "$OUT"
stamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT"; }
kubectl -n app scale deploy/parser --replicas=2 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=300s >/dev/null
stamp "delete all parser pods"
kubectl -n app delete pods -l app=parser --wait=false >/dev/null
for i in $(seq 1 90); do
  ready=$(kubectl -n app get endpoints parser -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)
  notready=$(kubectl -n app get endpoints parser -o jsonpath='{.subsets[*].notReadyAddresses[*].ip}' 2>/dev/null)
  code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d '{"text":"hi"}')
  stamp "ready endpoints: [${ready}]  not-ready: [${notready}]  /parse via Ingress -> HTTP ${code}"
  [ -n "$ready" ] && [ "$(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}')" = "2" ] && break
  sleep 2
done
stamp "done"
