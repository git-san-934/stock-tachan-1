"""ユニバース全社を分析してふるい（段階0〜⑥）を適用し、ランキングを作る。

  python scripts/build_shortlist.py

前提: data/<code>/financials.json（fetch_financials）と prices.json（fetch_prices）、
      data/market/commodities.json（fetch_market）が揃っていること。

出力:
  data/analysis/<code>.json  … 各社の全指標（analyze.py が書く）
  data/shortlist.json        … 一覧（pass_all → auto_score 降順）
"""
from __future__ import annotations

import argparse

from common import DATA, read_json, write_json
from analyze import analyze

FUNNEL_KEYS = ["s0_size", "s1_cheap", "s2_cyclical", "s3_trough",
               "s4_structural_ok", "s5_survivable", "s6_upside"]


def run(limit: int = 0) -> dict:
    universe = read_json(DATA / "universe.json", [])
    if limit:
        universe = universe[:limit]

    rows = []
    stats = {"total": 0, "analyzed": 0, "pass_all": 0}
    for i, u in enumerate(universe, 1):
        code = u["code"]
        stats["total"] += 1
        if not (DATA / code / "financials.json").exists():
            continue
        try:
            a = analyze(code)
        except Exception as err:  # noqa: BLE001
            print(f"  {code}: 分析エラー {err}")
            continue
        if not a:
            continue
        stats["analyzed"] += 1
        stats["pass_all"] += a["passes"]["pass_all"]
        v, t, s = a["valuation"], a["trough"], a["survival"]
        rows.append({
            "code": code, "name": a["name"], "sector33": a["sector33"],
            "market": a["market"], "price": a["price"],
            "market_cap_oku": a["market_cap_oku"], "n_years": a["n_years"],
            "auto_score": a["auto_score"],
            "pass_all": a["passes"]["pass_all"],
            "funnel": [a["passes"][k] for k in FUNNEL_KEYS],
            "expected_return_x": v["expected_return_x"],
            "normalized_per": v["normalized_per"], "pbr": v["pbr"],
            "cyclicality": a["cyclicality"]["score"],
            "trough_score": t["score"], "margin_pctile": t["margin_pctile"],
            "market_phase_score": t["market_phase_score"],
            "equity_ratio": s["equity_ratio"], "net_debt_to_equity": s["net_debt_to_equity"],
            "sales_cagr": a["structural"]["sales_cagr"],
            "downside_to_liquidation": a["liquidation"]["downside_to_liquidation"],
            "checklist": {k: a["checklist"][k]["mark"] for k in a["checklist"]},
        })
        if i % 100 == 0:
            print(f"  [{i}/{len(universe)}] analyzed={stats['analyzed']} "
                  f"pass_all={stats['pass_all']}")

    rows.sort(key=lambda r: (not r["pass_all"], -(r["auto_score"] or 0)))
    out = {"generated": _now(), "stats": stats, "rows": rows}
    write_json(DATA / "shortlist.json", out)
    print(f"\nshortlist: 分析 {stats['analyzed']} 社 / "
          f"pass_all {stats['pass_all']} 社 → {DATA / 'shortlist.json'}")
    return out


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    run(limit=args.limit)
