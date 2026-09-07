"""J-Quants API V2 の薄いラッパー。株価（最新終値）の更新にだけ使う。

V2 はダッシュボードで発行する API キーを `x-api-key` ヘッダで送る方式。
（V1 の /token/auth_user・/token/auth_refresh は廃止済み）

  .env / GitHub Secrets:  JQUANTS_API_KEY=xxxxxxxx

無料プランは直近12週間より前・約2年ぶんが対象。
"""
from __future__ import annotations

import time

import requests

from common import env, USER_AGENT

BASE = "https://api.jquants.com/v2"
# 無料プランは 60 req/分（1 req/秒）。超過すると 429、大幅超過で約5分ブロック。
_MIN_INTERVAL = 1.3
_last_call = [0.0]


def has_credentials() -> bool:
    return bool(env("JQUANTS_API_KEY"))


def _headers() -> dict:
    key = env("JQUANTS_API_KEY")
    if not key:
        raise SystemExit(
            "JQUANTS_API_KEY が未設定です。J-Quants のダッシュボードで API キーを発行し、"
            ".env と GitHub Secrets に JQUANTS_API_KEY=... を設定してください。")
    return {"x-api-key": key}


def _get(url: str, params: dict, hdr: dict) -> requests.Response:
    """1 req/秒を守り、429 は長めに待って1回だけ再試行する。"""
    for attempt in range(2):
        wait = _MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        resp = requests.get(url, params=params, headers=hdr, timeout=60)
        _last_call[0] = time.time()
        if resp.status_code == 429:
            if attempt == 0:
                print("  J-Quants 429（レート超過）。70秒待って再試行…")
                time.sleep(70)
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        return resp
    raise RuntimeError("unreachable")


def _paged(path: str, params: dict) -> list[dict]:
    hdr = {**_headers(), "User-Agent": USER_AGENT}
    rows: list[dict] = []
    key = None
    for _ in range(60):
        p = dict(params)
        if key:
            p["pagination_key"] = key
        payload = _get(f"{BASE}{path}", p, hdr).json()
        rows.extend(payload.get("data") or [])
        key = payload.get("pagination_key")
        if not key:
            break
    return rows


def daily_bars(*, date: str | None = None, code: str | None = None,
               date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """日次株価。date だけ指定で全銘柄の1日ぶん。

    返り値の各行: Date, Code, C(調整前終値), AdjC(調整後終値), AdjFactor, O/H/L/Vo/Va ...
    """
    params: dict = {}
    if date:
        params["date"] = date
    if code:
        params["code"] = code
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    return _paged("/equities/bars/daily", params)


def equities_master() -> list[dict]:
    """上場銘柄マスタ（V2: /equities/master）。"""
    return _paged("/equities/master", {})
