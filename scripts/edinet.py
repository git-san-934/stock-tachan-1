"""EDINET API v2: 書類一覧の取得（日付単位でキャッシュ）と書類ダウンロード。

- API キーは環境変数 EDINET_API_KEY もしくは .env から。
- 有価証券報告書 = docTypeCode "120"。
"""
from __future__ import annotations

import time
import zipfile
from pathlib import Path

from common import CACHE, env, http_get, download, read_json, write_json

API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
DOC_TYPE_YUHO = "120"


def get_api_key() -> str:
    key = env("EDINET_API_KEY")
    if not key:
        raise SystemExit(
            "EDINET_API_KEY が未設定です。.env に書くか環境変数で渡してください。")
    return key


def get_doc_list(date_str: str, *, use_cache: bool = True) -> dict:
    """指定日 (YYYY-MM-DD) の提出書類一覧。レスポンスは日付単位でキャッシュ。"""
    cache_file = CACHE / "doclist" / f"{date_str}.json"
    if use_cache and cache_file.exists():
        return read_json(cache_file, {})

    resp = http_get(f"{API_BASE}/documents.json",
                    params={"date": date_str, "type": 2,
                            "Subscription-Key": get_api_key()})
    payload = resp.json()
    write_json(cache_file, payload)
    time.sleep(0.15)
    return payload


def download_document(doc_id: str, doc_type: int, dest: Path,
                      *, retries: int = 3) -> Path:
    """書類取得API。doc_type: 1=XBRL ZIP, 2=PDF, 5=CSV(ZIP)。"""
    params = {"type": doc_type, "Subscription-Key": get_api_key()}
    last = b""
    for attempt in range(retries):
        download(f"{API_BASE}/documents/{doc_id}", dest, params=params)
        if doc_type in (1, 5):
            if zipfile.is_zipfile(dest):
                return dest
            last = dest.read_bytes()[:200]
            dest.unlink(missing_ok=True)
            if b'"status": "404"' in last or b'"status":"404"' in last:
                raise FileNotFoundError(f"{doc_id}: この書類に CSV はありません")
            time.sleep(2 * (attempt + 1))
        else:
            return dest
    raise RuntimeError(f"{doc_id}: zip でない応答 {last!r}")


def ensure_csv_zip(doc_id: str) -> Path:
    """有報 CSV(type=5) の ZIP をキャッシュに確保して返す。"""
    zip_path = CACHE / "docs" / doc_id / "csv.zip"
    if zip_path.exists() and zipfile.is_zipfile(zip_path):
        return zip_path
    zip_path.unlink(missing_ok=True)
    return download_document(doc_id, 5, zip_path)
