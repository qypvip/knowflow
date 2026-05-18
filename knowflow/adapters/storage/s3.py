from __future__ import annotations

"""
knowflow/adapters/storage/s3.py — S3-compatible storage
=========================================================
Requires: pip install knowflow[s3]  (installs boto3)

Config:
  bucket: str
  prefix: str (optional, default: "")
  region: str (optional, default: us-east-1)
  endpoint_url: str (optional, for MinIO/R2)
"""
from knowflow.core.storage import (
    StorageAdapter, StorageItem, StorageError, StorageNotFoundError
)


class S3Storage(StorageAdapter):
    """
    S3-compatible object storage backend.
    
    Works with: AWS S3, MinIO, Cloudflare R2, DigitalOcean Spaces, etc.
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self._import_check()
        import boto3
        self.bucket = config.get("bucket", "knowflow")
        self.prefix = config.get("prefix", "").strip("/")
        kwargs = {}
        if config.get("endpoint_url"):
            kwargs["endpoint_url"] = config["endpoint_url"]
        if config.get("region"):
            kwargs["region_name"] = config["region"]
        self.client = boto3.client("s3", **kwargs)
        # Ensure bucket exists
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)
    
    def _import_check(self):
        try:
            import boto3  # noqa
        except ImportError:
            raise StorageError(
                "S3 support requires boto3. Install: pip install knowflow[s3]"
            )
    
    def _key(self, path: str) -> str:
        return f"{self.prefix}/{path}".strip("/")
    
    def read(self, path: str) -> str:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
            return obj["Body"].read().decode("utf-8")
        except self.client.exceptions.NoSuchKey:
            raise StorageNotFoundError(f"Not found: {path}")
    
    def read_binary(self, path: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
            return obj["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise StorageNotFoundError(f"Not found: {path}")
    
    def write(self, path: str, content: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=self._key(path), Body=content.encode())
        return ""
    
    def write_binary(self, path: str, content: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=self._key(path), Body=content)
        return ""
    
    def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except Exception:
            return False
    
    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except Exception:
            return False
    
    def list(self, prefix: str = "") -> list[StorageItem]:
        key_prefix = self._key(prefix)
        response = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=key_prefix, Delimiter="/"
        )
        items = []
        for obj in response.get("Contents", []):
            name = obj["Key"][len(key_prefix):].lstrip("/")
            if name:
                items.append(StorageItem(
                    path=f"{prefix}/{name}".strip("/"),
                    size=obj["Size"],
                    modified_at=obj["LastModified"].timestamp(),
                ))
        return items
    
    def walk(self, prefix: str = "") -> list[StorageItem]:
        key_prefix = self._key(prefix)
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=key_prefix)
        items = []
        for obj in response.get("Contents", []):
            rel = obj["Key"][len(self.prefix):].lstrip("/") if self.prefix else obj["Key"]
            items.append(StorageItem(
                path=rel,
                size=obj["Size"],
                modified_at=obj["LastModified"].timestamp(),
            ))
        return items
