#!/usr/bin/env bash
# Task 3 evidence: (1) 50 sequential requests to a container limited to 1 CPU and 1 GiB, with peak memory;
# (2) FAULT_INJECT=1 makes /parse return HTTP 500 {"error":"invalid_model_output"}.
# Output: results/task3_50_requests.txt, results/task3_fault_inject.txt
set -uo pipefail
cd "$(dirname "$0")/.."
A=results/task3_50_requests.txt
F=results/task3_fault_inject.txt
: > "$A"; : > "$F"

kubectl -n app scale deploy/parser --replicas=1 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=300s >/dev/null
POD=$(kubectl -n app get pods -l app=parser --no-headers -o custom-columns=:metadata.name | head -1)
{
  echo "pod: $POD"
  echo "limits: $(kubectl -n app get pod "$POD" -o jsonpath='{.spec.containers[0].resources.limits}')"
  echo "memory before: $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.current) bytes"
  kubectl -n app exec "$POD" -- python - <<'EOF'
import json, time, urllib.request
cmds = [json.loads(l)["text"] for l in open("/dev/null")] or ["set an alarm for seven am", "what is the weather in london",
        "delete my appointment tomorrow", "what time is it in tokyo", "add running to my calendar for thursday"]
ok = 0; lat = []
for i in range(50):
    t = cmds[i % len(cmds)]
    s = time.time()
    r = urllib.request.urlopen(urllib.request.Request("http://localhost:8000/parse", json.dumps({"text": t}).encode(),
                               {"Content-Type": "application/json"}), timeout=60)
    body = r.read(); lat.append(time.time() - s)
    ok += r.status == 200
print(f"requests: 50, HTTP 200: {ok}, mean latency {sum(lat)/50:.2f}s, max {max(lat):.2f}s")
EOF
  echo "memory peak (cgroup memory.peak): $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.peak 2>/dev/null) bytes"
  echo "memory now: $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.current) bytes"
  echo "restarts: $(kubectl -n app get pod "$POD" -o jsonpath='{.status.containerStatuses[0].restartCount}'), last state: $(kubectl -n app get pod "$POD" -o jsonpath='{.status.containerStatuses[0].lastState}')"
  kubectl top pod "$POD" -n app
} 2>&1 | tee -a "$A"

echo "--- FAULT_INJECT=1" | tee -a "$F"
# keep the HPA from fighting the test
kubectl -n app set env deploy/parser FAULT_INJECT=1 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=400s | tee -a "$F"
for i in 1 2 3; do
  curl -s -m 30 -i -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d '{"text":"what is the weather in london"}' | grep -E '^HTTP/|^\{|error|X-Model' | tr -d '\r' | tee -a "$F"
done
kubectl -n app set env deploy/parser FAULT_INJECT- >/dev/null
kubectl -n app rollout status deploy/parser --timeout=400s | tee -a "$F"
echo "--- FAULT_INJECT removed; normal request:" | tee -a "$F"
curl -s -m 30 -i -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d '{"text":"what is the weather in london"}' | grep -E '^HTTP/|^\{' | tr -d '\r' | tee -a "$F"
kubectl -n app scale deploy/parser --replicas=2 >/dev/null
