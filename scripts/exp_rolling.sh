#!/usr/bin/env bash
# Task 4 steps 5 and 6: rolling update v1 -> v2 under load, rollback with `kubectl rollout undo`,
# then (still under load) delete one Pod and watch the replica count recover.
# Output: results/rolling_*.txt/.csv/.json, results/recovery_*.txt
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
OUT=results/rolling_update_log.txt
: > "$OUT"
stamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT"; }
probe() { curl -s -m 30 -D - -o /dev/null -X POST http://localhost:8080/parse -H 'Content-Type: application/json' \
          -d '{"text":"what is the weather in london"}' | grep -i -E '^HTTP/|x-model-version|x-served-by' | tr -d '\r' | tr '\n' ' '; echo; }

stamp "state before: $(kubectl -n app get deploy parser --no-headers | tr -s ' ')"
# keep exactly two replicas for the test; the HPA stays installed and wants 2 under load anyway
kubectl -n app scale deploy/parser --replicas=2 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=300s | tee -a "$OUT"

LOADTEST_HEADERS_OUT=results/rolling_load_headers.json $PY -m locust -f tools/locustfile.py --headless --users 4 \
  --spawn-rate 4 --run-time 9m --host http://localhost:8080 --csv results/rolling_load > results/rolling_load_stdout.txt 2>&1 &
LP=$!
sleep 45
stamp "baseline probe: $(probe)"

stamp "ROLLING UPDATE: set MODEL_VERSION=v2 MODEL_URI=s3://models/v2/"
kubectl -n app set env deploy/parser MODEL_VERSION=v2 MODEL_URI=s3://models/v2/ | tee -a "$OUT"
kubectl -n app rollout status deploy/parser --timeout=600s | tee -a "$OUT"
stamp "after update: $(probe)"
stamp "replicas: $(kubectl -n app get pods -l app=parser --no-headers | tr -s ' ' | tr '\n' ';')"
sleep 30

stamp "ROLLBACK: kubectl rollout undo"
kubectl -n app rollout undo deploy/parser | tee -a "$OUT"
kubectl -n app rollout status deploy/parser --timeout=600s | tee -a "$OUT"
for i in 1 2 3; do stamp "after rollback probe $i: $(probe)"; done
stamp "env after rollback: $(kubectl -n app get deploy parser -o jsonpath='{.spec.template.spec.containers[0].env[0:2]}')"
sleep 20

REC=results/recovery_log.txt
: > "$REC"
rstamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$REC"; }
VICTIM=$(kubectl -n app get pods -l app=parser --no-headers -o custom-columns=:metadata.name | head -1)
rstamp "RECOVERY: ready replicas before: $(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}'); deleting pod $VICTIM"
kubectl -n app delete pod "$VICTIM" --wait=false | tee -a "$REC"
for i in $(seq 1 40); do
  rstamp "ready replicas: $(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}') / $(kubectl -n app get deploy parser -o jsonpath='{.spec.replicas}')"
  [ "$(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}')" = "2" ] && break
  sleep 5
done
rstamp "recovered: $(kubectl -n app get pods -l app=parser --no-headers | tr -s ' ' | tr '\n' ';')"
wait $LP
stamp "load test finished"
