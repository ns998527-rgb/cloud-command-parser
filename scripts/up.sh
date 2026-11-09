#!/usr/bin/env bash
# Build and deploy the whole system on a local k3d cluster. Run via `make up`.
# Needs: docker, k3d, kubectl, python3 (with `pip install boto3`).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-$(command -v python3 || command -v python)}
CLUSTER=cloud-command-parser

echo "== 1/6 cluster"
k3d cluster list "$CLUSTER" >/dev/null 2>&1 || k3d cluster create --config cluster/k3d.yaml
kubectl config use-context "k3d-$CLUSTER" >/dev/null
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl apply -f k8s/00-namespaces.yaml

echo "== 2/6 secrets (generated now, never stored in Git)"
if kubectl -n data get secret s3-credentials >/dev/null 2>&1; then   # reuse the keys of an earlier run
  AK=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.access-key}' | base64 -d)
  SK=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.secret-key}' | base64 -d)
else
  AK=$($PY -c "import secrets;print('AK'+secrets.token_hex(8))")
  SK=$($PY -c "import secrets;print(secrets.token_hex(20))")
fi
kubectl -n data get secret seaweedfs-s3-config >/dev/null 2>&1 || \
  kubectl -n data create secret generic seaweedfs-s3-config --from-literal=s3.json="{\"identities\":[{\"name\":\"project\",\"credentials\":[{\"accessKey\":\"$AK\",\"secretKey\":\"$SK\"}],\"actions\":[\"Admin\",\"Read\",\"Write\",\"List\"]}]}"
for ns in data pipeline app; do
  kubectl -n "$ns" get secret s3-credentials >/dev/null 2>&1 || \
    kubectl -n "$ns" create secret generic s3-credentials --from-literal=access-key="$AK" --from-literal=secret-key="$SK"
done
export AWS_ACCESS_KEY_ID=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.access-key}' | base64 -d)
export AWS_SECRET_ACCESS_KEY=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.secret-key}' | base64 -d)

bash scripts/harden_cluster.sh

echo "== 3/6 object storage (SeaweedFS, namespace data)"
kubectl apply -f k8s/data/seaweedfs.yaml
kubectl -n data rollout status deploy/seaweedfs --timeout=300s

echo "== 4/6 buckets and uploads (models are fetched from the GitHub Release and verified)"
$PY scripts/fetch_models.py v1 v2
kubectl -n data port-forward svc/seaweedfs 8333:8333 >/tmp/pf-seaweedfs.log 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
for i in $(seq 1 30); do (echo > /dev/tcp/127.0.0.1/8333) 2>/dev/null && break; sleep 1; done
$PY scripts/seed_storage.py --endpoint http://localhost:8333
kill $PF 2>/dev/null || true

echo "== 5/6 images"
docker build -t command-parser:1.0 .
docker build -f worker/Dockerfile -t teacher-worker:1.0 .
k3d image import command-parser:1.0 teacher-worker:1.0 -c "$CLUSTER"

echo "== 6/6 application (namespace app)"
kubectl apply -f k8s/app/app.yaml
kubectl -n app rollout status deploy/parser --timeout=600s
echo "Ready. Try: curl -s -X POST localhost:8080/parse -H 'Content-Type: application/json' -d '{\"text\":\"what is the weather in london\"}'"
