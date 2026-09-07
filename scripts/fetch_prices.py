"""株価を Yahoo Finance の chart API（キー不要）から月次10年ぶん取得する。

  python scripts/fetch_prices.py 5401 5411 9101
  python scripts/fetch_prices.py --universe          # data/universe.json 全部
  python scripts/fetch_prices.py --universe --max-age-days 20   # 20日以内に取得済みはスキップ

CI（データセンターIP）では Yahoo が 429 を返しやすいので、ローカルで取得して
data/<code>/prices.json をコミットする運用にする。

出力: data/<code>/prices.json
  { "symbol": "5401.T", "as_of": "2026-09-05", "latest": 3210.0,
    "monthly": [["2016-09", 2450.0], ...],
    "pctile_10y": 0.34, "drawdown_from_peak_10y": 0.42, "chg_1y": -0.11 }
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timezone

from common import DATA, read_json, write_json, http_get, to_float, pct_rank

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"


def _yahoo_symbol(code: str) -> str:
    return f"{code.strip().upper()}.T"


def _fetch(code: str) -> dict | None:
    sym = _yahoo_symbol(code)
    resp = http_get(CHART.format(sym=sym),
                    params={"range": "10y", "interval": "1mo"},
                    headers={"Accept": "application/json"})
    data = resp.json()
    res = (data.get("chart") or {}).get("result") or []
    if not res:
        return None
    r = res[0]
    ts = r.get("timestamp") or []
    quote = (r.get("indicators", {}).get("quote") or [{}])[0]
    adj = (r.get("indicators", {}).get("adjclose") or [{}])
    closes = adj[0].get("adjclose") if adj and adj[0].get("adjclose") else quote.get("close")
    if not ts or not closes:
        return None

    monthly: list[list] = []
    for t, c in zip(ts, closes):
        v = to_float(c)
        if v is None:
            continue
        ym = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m")
        monthly.append([ym, round(v, 2)])
    if len(monthly) < 6:
        return None

    vals = [v for _, v in monthly]
    latest_v = vals[-1]
    peak = max(vals)
    chg_1y = None
    if len(monthly) >= 13 and monthly[-13][1]:
        chg_1y = latest_v / monthly[-13][1] - 1

    meta = r.get("meta") or {}
    spot = to_float(meta.get("regularMarketPrice")) or latest_v
    as_of = date.today().isoformat()
    if meta.get("regularMarketTime"):
        as_of = datetime.fromtimestamp(
            meta["regularMarketTime"], tz=timezone.utc).date().isoformat()

    return {
        "symbol": sym,
        "as_of": as_of,
        "latest": round(spot, 2),
        "monthly": monthly,
        "pctile_10y": round(pct_rank(spot, vals), 3),
        "drawdown_from_peak_10y": round((peak - spot) / peak, 3) if peak else None,
        "chg_1y": round(chg_1y, 3) if chg_1y is not None else None,
        "currency": meta.get("currency", "JPY"),
    }


def build(code: str, *, max_age_days: int = 0, sleep: float = 0.7) -> dict | None:
    out_path = DATA / code / "prices.json"
    if max_age_days and out_path.exists():
        prev = read_json(out_path, {})
        try:
            age = (date.today() - date.fromisoformat(prev.get("as_of", "2000-01-01"))).days
        except ValueError:
            age = 9999
        if age <= max_age_days:
            return prev
    try:
        rec = _fetch(code)
    except Exception as err:  # noqa: BLE001
        print(f"  {code}: 取得失敗 {err}")
        return None
    if not rec:
        print(f"  {code}: 株価データ無し")
        return None
    write_json(out_path, rec)
    print(f"  {code} {rec['symbol']}: {rec['latest']} "
          f"pctile10y={rec['pctile_10y']:.0%} DD={rec['drawdown_from_peak_10y']:.0%}")
    time.sleep(sleep)
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", help="証券コード（4桁）")
    ap.add_argument("--universe", action="store_true")
    ap.add_argument("--max-age-days", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.7)
    args = ap.parse_args()

    codes = args.codes
    if args.universe:
        codes = [r["code"] for r in read_json(DATA / "universe.json", [])]
    ok = fail = 0
    for i, c in enumerate(codes, 1):
        if args.universe and i % 50 == 0:
            print(f"[{i}/{len(codes)}]")
        r = build(c, max_age_days=args.max_age_days, sleep=args.sleep)
        ok += bool(r)
        fail += not r
    print(f"完了: 取得 {ok} / 失敗 {fail}")
