"""J-Quants API の薄いラッパー。上場銘柄マスタ（33業種区分）取得にだけ使う。

認証は次の優先順で解決する:
  1. JQUANTS_ID_TOKEN            … そのまま使う（24時間有効）
  2. JQUANTS_REFRESH_TOKEN       … /token/auth_refresh で ID トークンに交換（1週間有効）
  3. JQUANTS_MAIL + JQUANTS_PASS … /token/auth_user → refresh → id（CI 向き）

無料プランで /listed/info は利用可能。銘柄マスタなので12週遅延の影響はほぼ無い。
"""
from __future__ import annotations

import requests

from common import env, http_get

BASE = "https://api.jquants.com/v1"


def _id_token() -> str:
    tok = env("JQUANTS_ID_TOKEN")
    if tok:
        return tok

    refresh = env("JQUANTS_REFRESH_TOKEN")
    if not refresh:
        mail, pw = env("JQUANTS_MAIL"), env("JQUANTS_PASS")
        if mail and pw:
            r = requests.post(f"{BASE}/token/auth_user",
                              json={"mailaddress": mail, "password": pw}, timeout=30)
            r.raise_for_status()
            refresh = r.json()["refreshToken"]
    if not refresh:
        raise SystemExit(
            "J-Quants の認証情報がありません。.env に JQUANTS_REFRESH_TOKEN か "
            "JQUANTS_MAIL/JQUANTS_PASS を設定してください。"
            "（または fetch_universe.py --from-xlsx で JPX の銘柄一覧を使う）")

    r = requests.post(f"{BASE}/token/auth_refresh",
                      params={"refreshtoken": refresh}, timeout=30)
    r.raise_for_status()
    return r.json()["idToken"]


def listed_info() -> list[dict]:
    """全上場銘柄のマスタ（Code, CompanyName, Sector33CodeName, MarketCodeName ...）。"""
    token = _id_token()
    resp = http_get(f"{BASE}/listed/info",
                    headers={"Authorization": f"Bearer {token}"})
    return resp.json().get("info", [])
