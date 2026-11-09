"""Create the buckets and upload inputs to object storage (SeaweedFS S3), run from the host.

Usage: python scripts/seed_storage.py --endpoint http://localhost:8333 [--models-dir models]
Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in the environment.

Uploads
  datasets/commands_pool.jsonl, datasets/teacher/shard-*.jsonl, datasets/v1/train.jsonl + train.sha256
  models/v1/*, models/v2/*   (only the model directories that exist under --models-dir)
"""
import argparse
import glob
import os

import boto3
from botocore.exceptions import ClientError


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--models-dir", default="models")
    a = ap.parse_args()
    s3 = boto3.client("s3", endpoint_url=a.endpoint, region_name="us-east-1")

    for b in ("datasets", "models"):
        try:
            s3.create_bucket(Bucket=b)
            print("created bucket", b)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise
            print("bucket exists", b)

    uploads = [("data/commands_pool.jsonl", "datasets", "commands_pool.jsonl")]
    uploads += [(p, "datasets", "teacher/" + os.path.basename(p)) for p in sorted(glob.glob("datasets/teacher/shard-*.jsonl"))]
    uploads += [(p, "datasets", "v1/" + os.path.basename(p)) for p in ("datasets/v1/train.jsonl", "datasets/v1/train.sha256") if os.path.exists(p)]
    for v in ("v1", "v2"):
        d = os.path.join(a.models_dir, v)
        if os.path.isdir(d):
            uploads += [(os.path.join(d, n), "models", f"{v}/{n}") for n in sorted(os.listdir(d))]
    for path, bucket, key in uploads:
        s3.upload_file(path, bucket, key)
        print(f"uploaded {path} -> s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
