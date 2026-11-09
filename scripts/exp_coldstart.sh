#!/usr/bin/env bash
# Task 4 step 7: delete all Pods three times; record Pod creation -> Ready time and the model-download log lines.
# Also records the Service endpoints while the model is still loading (they must be empty).
# Output: results/coldstart.txt, results/coldstart_logs.txt
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=results/coldstart.txt
LOGS=results/coldstart_logs.txt
: > "$OUT"; : > "$LOGS"
stamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT"; }

kubectl -n app scale deploy/parser --replicas=2 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=300s >/dev/null
for run in 1 2 3; do
  stamp "=== run $run: delete all parser pods"
  kubectl -n app delete pods -l app=parser --wait=false >/dev/null
  # watch endpoints until the first pod is ready
  for i in $(seq 1 120); do
    ep=$(kubectl -n app get endpointslices -l kubernetes.io/service-name=parser -o jsonpath='{.items[*].endpoints[*].addresses[0]}' 2>/dev/null)
    ready=$(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}')
    stamp "ready pods: ${ready:-0}  ready endpoints: [${ep}]"
    [ "${ready:-0}" = "2" ] && break
    sleep 3
  done
  for p in $(kubectl -n app get pods -l app=parser --no-headers -o custom-columns=:metadata.name); do
    created=$(kubectl -n app get pod "$p" -o jsonpath='{.metadata.creationTimestamp}')
    readyt=$(kubectl -n app get pod "$p" -o jsonpath='{.status.conditions[?(@.type=="Ready")].lastTransitionTime}')
    secs=$(python -c "from datetime import datetime as d;f='%Y-%m-%dT%H:%M:%SZ';print(int((d.strptime('$readyt',f)-d.strptime('$created',f)).total_seconds()))")
    stamp "run $run pod $p created $created ready $readyt  => ${secs}s"
    echo "run=$run pod=$p seconds=$secs" >> results/coldstart_seconds.txt
    { echo "--- run $run pod $p"; kubectl -n app logs "$p" | grep -E "loading model|downloaded|model ready"; } >> "$LOGS"
  done
done
