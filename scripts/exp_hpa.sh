#!/usr/bin/env bash
# Task 4 step 4: show the HPA scaling 1 -> 2 replicas under load and back down to 1.
# Output: results/hpa_scaling.txt (timestamped `kubectl get hpa` samples) and results/hpa_load_*.csv
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
OUT=results/hpa_scaling.txt
: > "$OUT"
stamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT"; }
sample() { stamp "$(kubectl -n app get hpa parser --no-headers 2>&1 | tr -s ' ') | spec replicas: $(kubectl -n app get deploy parser -o jsonpath='{.spec.replicas}') ready: $(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}')"; }

stamp "phase 1: wait for the idle HPA to scale down to 1 replica"
for i in $(seq 1 60); do
  sample
  [ "$(kubectl -n app get deploy parser -o jsonpath='{.spec.replicas}')" = "1" ] && break
  sleep 15
done

stamp "phase 2: start load (4 users, 4 minutes) and sample every 15 s"
LOADTEST_HEADERS_OUT=results/hpa_load_headers.json $PY -m locust -f tools/locustfile.py --headless --users 4 \
  --spawn-rate 4 --run-time 4m --host http://localhost:8080 --csv results/hpa_load > results/hpa_load_stdout.txt 2>&1 &
LP=$!
for i in $(seq 1 17); do sample; sleep 15; done
wait $LP

stamp "phase 3: load stopped, wait for scale back down to 1 (HPA stabilisation window is 5 minutes)"
for i in $(seq 1 60); do
  sample
  [ "$(kubectl -n app get deploy parser -o jsonpath='{.spec.replicas}')" = "1" ] && break
  sleep 15
done
stamp "done"
