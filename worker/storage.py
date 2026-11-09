"""Tiny storage helper: a path is either a local file/dir or an s3://bucket/key URI.

S3 access uses boto3 with S3_ENDPOINT (SeaweedFS) and credentials from the
standard AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY environment variables.
"""
import os


def _client():
    import boto3
    return boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT") or None,
                        region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _split(uri):
    bucket, _, key = uri[len("s3://"):].partition("/")
    return bucket, key


def is_s3(uri):
    return uri.startswith("s3://")


def read_text(uri):
    if is_s3(uri):
        b, k = _split(uri)
        return _client().get_object(Bucket=b, Key=k)["Body"].read().decode("utf-8")
    with open(uri, encoding="utf-8", newline="") as f:
        return f.read()


def write_bytes(uri, data):
    if is_s3(uri):
        b, k = _split(uri)
        _client().put_object(Bucket=b, Key=k, Body=data)
        return
    os.makedirs(os.path.dirname(uri) or ".", exist_ok=True)
    with open(uri, "wb") as f:
        f.write(data)


def write_text(uri, text):
    write_bytes(uri, text.encode("utf-8"))


def list_keys(uri_prefix):
    """List full URIs under a prefix (S3) or files in a directory (local), sorted."""
    if is_s3(uri_prefix):
        b, k = _split(uri_prefix)
        out = []
        for page in _client().get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=k):
            out += [f"s3://{b}/{o['Key']}" for o in page.get("Contents", [])]
        return sorted(out)
    return sorted(os.path.join(uri_prefix, n) for n in os.listdir(uri_prefix))
