"""市況シリーズを FRED から取得し、フェーズ判定用の指標に加工する。

FRED の CSV は API キー不要:
  https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series>

出力: data/market/commodities.json
  { "iron_ore": {
      "label": "...", "as_of": "2026-08", "latest": 105.3,
      "monthly": [["2010-01", 130.0], ...],   # 直近15年・月次
      "pctile_15y": 0.22,                     # 15年内の下位パーセンタイル
      "yoy": -0.18, "chg_3m": -0.05,
      "phase_hint": "谷寄り"                   # 谷寄り / 中立 / 山寄り
    }, ... }
"""
from __future__ import annotations

import csv
import io
from datetime import date

from common import DATA, load_config, write_json, http_get, to_float, pct_rank

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def _fetch_fred_monthly(series_id: str) -> list[tuple[str, float]]:
    resp = http_get(FRED_CSV.format(sid=series_id))
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader, None)
    out: dict[str, float] = {}
    for row in reader:
        if len(row) < 2:
            continue
        d, raw = row[0].strip(), row[1].strip()
        v = to_float(raw)
        if v is None:
            continue
        out[d[:7]] = v  # 同月は後勝ち（月末値に寄せる）
    return sorted(out.items())


def _phase_hint(pctile: float | None, yoy: float | None) -> str:
    if pctile is None:
        return "不明"
    if pctile <= 0.30 and (yoy is None or yoy <= 0.05):
        return "谷寄り"
    if pctile >= 0.70:
        return "山寄り"
    return "中立"


def build() -> dict:
    cfg = load_config("sectors.json")
    sources = cfg["commodity_sources"]
    cutoff = f"{date.today().year - 15}-01"
    result: dict = {}

    for key, src in sources.items():
        if src.get("provider") != "fred" or not src.get("series"):
            result[key] = {"label": src.get("label", key), "manual": True}
            continue
        try:
            monthly_all = _fetch_fred_monthly(src["series"])
        except Exception as err:  # noqa: BLE001
            print(f"  {key} ({src['series']}): 取得失敗 {err}")
            result[key] = {"label": src.get("label", key), "error": str(err)}
            continue

        monthly = [(m, v) for m, v in monthly_all if m >= cutoff]
        if not monthly:
            result[key] = {"label": src.get("label", key), "error": "データ無し"}
            continue

        vals = [v for _, v in monthly]
        latest_m, latest_v = monthly[-1]
        pctile = pct_rank(latest_v, vals)
        yoy = None
        if len(monthly) >= 13 and monthly[-13][1]:
            yoy = latest_v / monthly[-13][1] - 1
        chg_3m = None
        if len(monthly) >= 4 and monthly[-4][1]:
            chg_3m = latest_v / monthly[-4][1] - 1

        ly, lm = int(latest_m[:4]), int(latest_m[5:7])
        months_old = (date.today().year - ly) * 12 + (date.today().month - lm)
        result[key] = {
            "label": src.get("label", key),
            "as_of": latest_m,
            "stale": months_old > 6,
            "latest": round(latest_v, 3),
            "monthly": [[m, round(v, 3)] for m, v in monthly],
            "pctile_15y": round(pctile, 3) if pctile is not None else None,
            "yoy": round(yoy, 3) if yoy is not None else None,
            "chg_3m": round(chg_3m, 3) if chg_3m is not None else None,
            "phase_hint": _phase_hint(pctile, yoy),
        }
        print(f"  {key}: {latest_m} {latest_v:.1f} "
              f"pctile={pctile:.0%} yoy={yoy if yoy is None else f'{yoy:+.0%}'} "
              f"-> {result[key]['phase_hint']}")

    write_json(DATA / "market" / "commodities.json", result)
    return result


if __name__ == "__main__":
    build()
