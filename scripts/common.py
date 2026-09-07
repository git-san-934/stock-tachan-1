"""共通ユーティリティ: パス・.env 読み込み・HTTP・JSON 入出力。

依存は requests / openpyxl のみ（numpy 等は使わない）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Windows のコンソール既定が cp932 でも UTF-8 で出力する
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DATA = ROOT / "data"
CONFIG = ROOT / "config"

USER_AGENT = "stock-tachan-1/0.1 (cyclical value screener; contact via GitHub)"


# ---------------------------------------------------------------- .env

def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def env(name: str, default: str = "") -> str:
    load_dotenv()
    return os.environ.get(name, default).strip()


# ---------------------------------------------------------------- HTTP

def http_get(url: str, *, params: dict | None = None, stream: bool = False,
             timeout: int = 60, retries: int = 3, backoff: float = 2.0,
             headers: dict | None = None) -> requests.Response:
    hdr = {"User-Agent": USER_AGENT}
    if headers:
        hdr.update(headers)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, stream=stream,
                                timeout=timeout, headers=hdr)
            resp.raise_for_status()
            return resp
        except Exception as err:  # noqa: BLE001 - 通信エラーは全部リトライ
            last = err
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"GET 失敗: {url} ({last})")


def download(url: str, dest: Path, *, params: dict | None = None,
             timeout: int = 120) -> Path:
    resp = http_get(url, params=params, stream=True, timeout=timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            fh.write(chunk)
    return dest


# ---------------------------------------------------------------- JSON

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config(name: str) -> Any:
    return read_json(CONFIG / name)


# ---------------------------------------------------------------- 証券コード

def norm_seccode(code: str) -> str:
    """4桁→5桁（末尾0付与）。EDINET の secCode は5桁。"""
    code = str(code).strip().upper()
    return code + "0" if len(code) == 4 else code


def short_seccode(code: str) -> str:
    """5桁→4桁（表示・ディレクトリ名用）。"""
    code = norm_seccode(code)
    return code[:-1] if len(code) == 5 else code


# ---------------------------------------------------------------- 数値

def to_float(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s in ("", "-", "－", "―", "NA", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float] | None:
    """単回帰 y = a + b x を最小二乗で解く。(a, b, r2) を返す。点が3未満なら None。"""
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pts)
    if n < 3:
        return None
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    mx, my = sx / n, sy / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    if sxx == 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    sst = sum((y - my) ** 2 for _, y in pts)
    ssr = sum((y - (a + b * x)) ** 2 for x, y in pts)
    r2 = 1 - ssr / sst if sst else 0.0
    return a, b, r2


def pct_rank(value: float | None, series: list[float]) -> float | None:
    """value が series の中で下から何パーセンタイルかを 0..1 で返す。"""
    vals = [v for v in series if v is not None]
    if value is None or not vals:
        return None
    below = sum(1 for v in vals if v <= value)
    return below / len(vals)


def median(series: list[float]) -> float | None:
    vals = sorted(v for v in series if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2


def stdev(series: list[float]) -> float | None:
    vals = [v for v in series if v is not None]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


def cagr(first: float | None, last: float | None, years: float) -> float | None:
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1
