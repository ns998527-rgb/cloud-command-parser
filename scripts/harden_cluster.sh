#!/usr/bin/env bash
# The k3d node shares a small laptop (4 threads, ~7.7 GB RAM) with Windows. Under load, the built-in
# system pods (Traefik, CoreDNS, metrics-server) missed their health probes and were restarted, which
# briefly broke the Ingress. Give their probes generous timeouts so that a short stall is not fatal.
set -euo pipefail

kubectl apply -f - <<'EOF'
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    livenessProbe:
      failureThreshold: 10
      initialDelaySeconds: 5
      periodSeconds: 10
      successThreshold: 1
      timeoutSeconds: 10
    readinessProbe:
      failureThreshold: 10
      initialDelaySeconds: 5
      periodSeconds: 10
      successThreshold: 1
      timeoutSeconds: 10
EOF

relax() {  # relax <deployment> <container>
  kubectl -n kube-system patch deploy "$1" --type strategic -p "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"$2\",
    \"livenessProbe\":{\"timeoutSeconds\":10,\"failureThreshold\":10},
    \"readinessProbe\":{\"timeoutSeconds\":10,\"failureThreshold\":10}}]}}}}" >/dev/null
}
relax coredns coredns
relax metrics-server metrics-server
kubectl -n kube-system rollout status deploy/coredns --timeout=180s
kubectl -n kube-system rollout status deploy/metrics-server --timeout=180s
echo "cluster system pods hardened"
