from __future__ import annotations

"""
knowflow/adapters/storage/webdav.py — WebDAV storage backend
=============================================================
WebDAV protocol — works with: NextCloud, Synology NAS, ownCloud, etc.

Config:
  base_url: str   — WebDAV endpoint (e.g. https://nextcloud.example.com/remote.php/dav/files/user)
  username: str   — WebDAV username
  password: str   — WebDAV password or app token
  path: str       — Root path within WebDAV (default: /KnowFlow)

Requires: requests (already installed in the environment)
"""
import os
import json
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from knowflow.core.storage import (
    StorageAdapter, StorageItem, StorageError, StorageNotFoundError
)


WEBDAV_NS = {
    "d": "DAV:",
}


class WebDAVStorage(StorageAdapter):
    """
    WebDAV 存储后端

    兼容：
      - NextCloud
      - Synology Drive
      - ownCloud
      - Apache mod_dav
      - 任何标准 WebDAV 服务
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        cfg = config or {}
        self.base_url = cfg["base_url"].rstrip("/")
        self.auth = (cfg.get("username", ""), cfg.get("password", ""))
        self.root = cfg.get("path", "/KnowFlow").rstrip("/")
        self._session = None
        self._check()

    @property
    def _http(self):
        """Lazy-import requests to avoid hard dependency"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.auth = self.auth
            self._session.headers.update({
                "User-Agent": "KnowFlow/0.1.0",
            })
        return self._session

    def _check(self):
        """验证连接"""
        try:
            resp = self._http.request("PROPFIND", f"{self.base_url}{self.root}",
                                       headers={"Depth": "0"}, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            raise StorageError(
                f"WebDAV 连接失败: {e}\n"
                f"  URL: {self.base_url}{self.root}\n"
                f"  请检查 base_url/username/password 是否正确"
            )

    def _url(self, path: str) -> str:
        """相对路径 → 完整 URL"""
        clean = path.lstrip("/")
        full = f"{self.root}/{clean}"
        return f"{self.base_url}{full}"

    def _parse_propfind(self, xml: str) -> list[StorageItem]:
        """解析 PROPFIND 响应 XML → StorageItem 列表"""
        items = []
        root = ET.fromstring(xml)
        for resp in root.findall("d:response", WEBDAV_NS):
            href = resp.findtext("d:href", "", WEBDAV_NS)
            if not href:
                continue

            # 取相对路径
            rel = href.replace(self.base_url, "").replace(self.root, "").strip("/")
            if not rel:
                continue

            prop = resp.find("d:propstat/d:prop", WEBDAV_NS)
            if prop is None:
                continue

            is_dir = prop.find("d:resourcetype/d:collection", WEBDAV_NS) is not None
            size_text = prop.findtext("d:getcontentlength", "0", WEBDAV_NS)
            size = int(size_text) if size_text.isdigit() else 0
            mtime_text = prop.findtext("d:getlastmodified", "", WEBDAV_NS)
            mtime = 0
            if mtime_text:
                import email.utils
                try:
                    mtime = email.utils.parsedate_to_datetime(mtime_text).timestamp()
                except Exception:
                    pass

            items.append(StorageItem(
                path=rel,
                size=size,
                modified_at=mtime,
                is_dir=is_dir,
            ))
        return items

    def read(self, path: str) -> str:
        resp = self._http.get(self._url(path), timeout=30)
        if resp.status_code == 404:
            raise StorageNotFoundError(f"Not found: {path}")
        resp.raise_for_status()
        return resp.text

    def read_binary(self, path: str) -> bytes:
        resp = self._http.get(self._url(path), timeout=30)
        if resp.status_code == 404:
            raise StorageNotFoundError(f"Not found: {path}")
        resp.raise_for_status()
        return resp.content

    def write(self, path: str, content: str) -> str:
        self._ensure_parent(path)
        resp = self._http.put(self._url(path), data=content.encode("utf-8"), timeout=60)
        resp.raise_for_status()
        return ""

    def write_binary(self, path: str, content: bytes) -> str:
        self._ensure_parent(path)
        resp = self._http.put(self._url(path), data=content, timeout=60)
        resp.raise_for_status()
        return ""

    def delete(self, path: str) -> bool:
        resp = self._http.request("DELETE", self._url(path), timeout=30)
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def exists(self, path: str) -> bool:
        resp = self._http.request("PROPFIND", self._url(path),
                                   headers={"Depth": "0"}, timeout=15)
        return resp.status_code == 207  # Multi-Status = found

    def list(self, prefix: str = "") -> list[StorageItem]:
        url = self._url(prefix) if prefix else f"{self.base_url}{self.root}"
        resp = self._http.request("PROPFIND", url,
                                   headers={"Depth": "1"}, timeout=30)
        if resp.status_code != 207:
            return []
        all_items = self._parse_propfind(resp.text)
        # 排除自身
        root_name = prefix.rstrip("/").split("/")[-1] if prefix else ""
        return [i for i in all_items if i.path != root_name and i.path]

    def walk(self, prefix: str = "") -> list[StorageItem]:
        """递归列出所有文件"""
        url = self._url(prefix) if prefix else f"{self.base_url}{self.root}"
        resp = self._http.request("PROPFIND", url,
                                   headers={"Depth": "infinity"}, timeout=60)
        if resp.status_code != 207:
            return []
        all_items = self._parse_propfind(resp.text)
        root_name = prefix.rstrip("/").split("/")[-1] if prefix else ""
        return [i for i in all_items if i.path != root_name and i.path and not i.is_dir]

    def _ensure_parent(self, path: str):
        """确保父目录存在（通过 PROPFIND + MKCOL）"""
        parent = Path(path).parent.as_posix().strip("/")
        if not parent or parent == ".":
            return
        parts = parent.split("/")
        current = f"{self.base_url}{self.root}"
        for part in parts:
            current = f"{current}/{quote(part, safe='')}"
            resp = self._http.request("PROPFIND", current,
                                       headers={"Depth": "0"}, timeout=15)
            if resp.status_code != 207:
                # 目录不存在，创建
                resp = self._http.request("MKCOL", current, timeout=15)
                if resp.status_code not in (201, 405):  # 201 Created, 405 Already exists
                    resp.raise_for_status()
