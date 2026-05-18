from __future__ import annotations

"""
knowflow/adapters/storage/quark.py — 夸克网盘 storage backend
==============================================================
Requires: kuake_cli installed + cookie configured.

Config:
  path: str  (default: /KnowFlow)  — 夸克网盘内的根目录
  temp_dir: str  (default: /tmp/knowflow-quark)  — 本地缓存目录

由于夸克网盘没有文件系统操作（没有 stat/mtime），
本适配器用本地 temp_dir 做缓存，同步到夸克。
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from knowflow.core.storage import (
    StorageAdapter, StorageItem, StorageError, StorageNotFoundError
)


KUAKE_HOME = os.path.expanduser("~/.config/kuake")


class QuarkStorage(StorageAdapter):
    """
    夸克网盘存储后端

    工作方式：
      - 读：先从夸克下载到本地缓存 → 读缓存
      - 写：先写本地缓存 → 再上传到夸克
      - 列表：调 kuake list
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        cfg = config or {}
        self.remote_root = cfg.get("path", "/KnowFlow").rstrip("/")
        self.temp_dir = Path(cfg.get("temp_dir", "/tmp/knowflow-quark"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._check_kuake()

    def _check_kuake(self):
        """验证 kuake 可用"""
        try:
            result = subprocess.run(
                ["kuake", "user"],
                capture_output=True, text=True, timeout=15,
                cwd=KUAKE_HOME,
            )
            if result.returncode != 0:
                raise StorageError(
                    f"夸克网盘连接失败。请检查 cookie 是否过期。\n"
                    f"  {result.stderr.strip()}"
                )
        except FileNotFoundError:
            raise StorageError(
                "未找到 kuake 命令。请安装: https://github.com/kuake-cli/kuake"
            )

    def _kuake(self, *args, timeout=60) -> str:
        """执行 kuake 命令"""
        try:
            result = subprocess.run(
                ["kuake", *args],
                capture_output=True, text=True, timeout=timeout,
                cwd=KUAKE_HOME,
            )
            if result.returncode != 0:
                raise StorageError(
                    f"kuake {' '.join(args)} 失败: {result.stderr.strip()}"
                )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise StorageError(f"kuake 命令超时 ({timeout}s)")

    def _local_path(self, path: str) -> Path:
        """远程路径 → 本地缓存路径"""
        clean = path.lstrip("/")
        return self.temp_dir / clean

    def _remote_path(self, path: str) -> str:
        """相对路径 → 夸克完整路径"""
        return f"{self.remote_root}/{path.lstrip('/')}"

    def _ensure_remote_dirs(self, path: str):
        """确保夸克远程目录存在"""
        parent = Path(path).parent.as_posix().strip("/")
        # 文件在根目录（如 hello.txt），无需创建目录
        if not parent or parent == ".":
            return
        parts = parent.split("/")
        current = self.remote_root
        for part in parts:
            current = f"{current}/{part}"
            exists = False
            try:
                self._kuake("list", current, timeout=15)
                exists = True
            except StorageError:
                pass
            if not exists:
                parent = current.rsplit("/", 1)[0] if "/" in current else ""
                self._kuake("create", part, parent, timeout=15)

    def read(self, path: str) -> str:
        local = self._local_path(path)
        if not local.exists():
            self._download(path)
        return local.read_text(encoding="utf-8")

    def read_binary(self, path: str) -> bytes:
        local = self._local_path(path)
        if not local.exists():
            self._download(path)
        return local.read_bytes()

    def write(self, path: str, content: str) -> str:
        local = self._local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(content, encoding="utf-8")
        self._upload(path)
        return ""

    def write_binary(self, path: str, content: bytes) -> str:
        local = self._local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
        self._upload(path)
        return ""

    def delete(self, path: str) -> bool:
        remote = self._remote_path(path)
        local = self._local_path(path)
        try:
            self._kuake("delete", remote)
        except StorageError:
            pass
        if local.exists():
            local.unlink()
        return True

    def exists(self, path: str) -> bool:
        """检查文件是否存在（先查本地缓存，再查夸克远程）"""
        # 1. 查本地缓存
        local = self._local_path(path)
        if local.exists():
            return True
        # 2. 查夸克远程（用 list 查父目录）
        parent_dir = Path(path).parent.as_posix().strip("/")
        try:
            items = self.list(parent_dir)
            target = Path(path).name
            return any(i.path == target for i in items)
        except StorageError:
            return False

    def list(self, prefix: str = "") -> list[StorageItem]:
        remote = self._remote_path(prefix) if prefix else self.remote_root
        try:
            output = self._kuake("list", remote, timeout=30)
        except StorageError:
            return []

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []

        items = []
        for entry in data.get("data", {}).get("list", []):
            items.append(StorageItem(
                path=entry.get("file_name", ""),
                size=entry.get("size", 0),
                modified_at=0,  # 夸克API不提供mtime
                is_dir=entry.get("dir", False),
                etag=entry.get("fid", ""),
            ))
        return items

    def walk(self, prefix: str = "") -> list[StorageItem]:
        """递归列出所有文件（夸克API不支持递归，只能逐层遍历）"""
        items = []
        queue = [prefix]
        seen = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            try:
                children = self.list(current)
            except StorageError:
                continue
            for child in children:
                full_path = f"{current}/{child.path}".strip("/")
                if child.is_dir:
                    queue.append(full_path)
                else:
                    items.append(StorageItem(
                        path=full_path,
                        size=child.size,
                        modified_at=child.modified_at,
                        etag=child.etag,
                    ))
        return items

    def _download(self, path: str):
        """从夸克下载文件到本地缓存"""
        remote = self._remote_path(path)
        local = self._local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        self._kuake("download", remote, str(local), timeout=120)

    def _upload(self, path: str):
        """从本地缓存上传到夸克"""
        local = self._local_path(path)
        if not local.exists():
            raise StorageNotFoundError(f"本地缓存不存在: {path}")
        self._ensure_remote_dirs(path)
        remote = self._remote_path(path)
        self._kuake("upload", str(local), remote, timeout=120)
