#!/usr/bin/env bash
# Task 3 evidence: 50 sequential requests to one container limited to 1 CPU and 1 GiB, with peak memory.
# Output: results/task3_50_requests.txt
set -uo pipefail
export MSYS_NO_PATHCONV=1   # keep /sys/... paths intact under Git Bash
cd "$(dirname "$0")/.."
A=results/task3_50_requests.txt
: > "$A"
kubectl -n app scale deploy/parser --replicas=1 >/dev/null
kubectl -n app rollout status deploy/parser --timeout=400s >/dev/null
sleep 20
POD=$(kubectl -n app get pods -l app=parser --field-selector=status.phase=Running --no-headers -o custom-columns=:metadata.name | head -1)
{
  echo "pod: $POD   (replicas: $(kubectl -n app get deploy parser -o jsonpath='{.status.readyReplicas}'))"
  echo "limits: $(kubectl -n app get pod "$POD" -o jsonpath='{.spec.containers[0].resources.limits}')"
  echo "memory before: $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.current) bytes"
  kubectl -n app exec -i "$POD" -- python - <<'EOF'
import json, time, urllib.request
cmds = ["set an alarm for seven am", "what is the weather in london", "delete my appointment tomorrow",
        "what time is it in tokyo", "add running to my calendar for thursday"]
ok = 0; lat = []
for i in range(50):
    s = time.time()
    r = urllib.request.urlopen(urllib.request.Request("http://localhost:8000/parse", json.dumps({"text": cmds[i % 5]}).encode(),
                               {"Content-Type": "application/json"}), timeout=60)
    r.read(); lat.append(time.time() - s); ok += r.status == 200
lat.sort()
print(f"requests: 50 one after another, HTTP 200: {ok}, mean {sum(lat)/50:.2f}s, median {lat[25]:.2f}s, max {lat[-1]:.2f}s")
EOF
  echo "memory peak (cgroup memory.peak): $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.peak) bytes"
  echo "memory now: $(kubectl -n app exec "$POD" -- cat /sys/fs/cgroup/memory.current) bytes"
  echo "restarts: $(kubectl -n app get pod "$POD" -o jsonpath='{.status.containerStatuses[0].restartCount}'), OOMKilled: $(kubectl -n app get pod "$POD" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}')"
  kubectl top pod "$POD" -n app
} 2>&1 | tee -a "$A"
kubectl -n app scale deploy/parser --replicas=2 >/dev/null
