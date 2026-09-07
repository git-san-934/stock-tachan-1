"""対象ユニバースを作る: 全上場銘柄 → 33業種でシクリカル業種だけに絞る。

  python scripts/fetch_universe.py                # J-Quants /listed/info から
  python scripts/fetch_universe.py --from-xlsx    # cache/universe.xlsx（JPX data_j を .xlsx 保存したもの）から

出力: data/universe.json
  [{ "code": "5401", "name": "日本製鉄", "sector33": "鉄鋼",
     "market": "プライム", "commodities": ["iron_ore", "coal_coking"] }, ...]
"""
from __future__ import annotations

import argparse

from common import DATA, CACHE, load_config, write_json, short_seccode

CYCLICAL: set[str] = set()
SECTOR_COMMODITIES: dict[str, list[str]] = {}


def _load_cfg() -> None:
    cfg = load_config("sectors.json")
    CYCLICAL.update(cfg["cyclical_sectors"])
    SECTOR_COMMODITIES.update(cfg["sector_commodities"])


def _from_jquants() -> list[dict]:
    """J-Quants V2 の銘柄マスタから。フィールド名は仕様変更されうるので候補で拾う。"""
    from jquants import equities_master

    def pick(row, *names):
        for n in names:
            if row.get(n) not in (None, ""):
                return str(row[n]).strip()
        return ""

    rows = []
    for r in equities_master():
        sector = pick(r, "Sector33CodeName", "Sector33Name", "Sec33Name")
        market = pick(r, "MarketCodeName", "MarketName", "MktName")
        code = short_seccode(pick(r, "Code", "LocalCode"))
        name = pick(r, "CompanyName", "Name", "CoName")
        if not code or sector in ("", "-", "その他") or "ETF" in market or "REIT" in market:
            continue
        rows.append({"code": code, "name": name, "sector33": sector, "market": market})
    return rows


def _from_seed() -> list[dict]:
    import csv
    from common import CONFIG
    path = CONFIG / "universe_seed.csv"
    rows = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"code": short_seccode(r["code"]), "name": r["name"].strip(),
                         "sector33": r["sector33"].strip(), "market": ""})
    return rows


def _from_xlsx() -> list[dict]:
    import openpyxl
    path = CACHE / "universe.xlsx"
    if not path.exists():
        raise SystemExit(f"{path} がありません。JPX の data_j.xls をブラウザで開き "
                         "『.xlsx』で保存して cache/universe.xlsx に置いてください。")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    header = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]

    def col(*names: str) -> int:
        for n in names:
            if n in header:
                return header.index(n)
        raise SystemExit(f"列が見つかりません: {names} / 実際の見出し: {header}")

    ci, cn, cs, cm = (col("コード"), col("銘柄名"),
                      col("33業種区分"), col("市場・商品区分"))
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        code = str(r[ci] or "").strip()
        if not code:
            continue
        rows.append({"code": short_seccode(code), "name": str(r[cn] or "").strip(),
                     "sector33": str(r[cs] or "").strip(),
                     "market": str(r[cm] or "").strip()})
    return rows


def build(source: str) -> list[dict]:
    _load_cfg()
    allrows = {"xlsx": _from_xlsx, "seed": _from_seed,
               "jquants": _from_jquants}[source]()
    universe = []
    for r in allrows:
        if r["sector33"] not in CYCLICAL:
            continue
        r["commodities"] = SECTOR_COMMODITIES.get(r["sector33"], [])
        universe.append(r)
    universe.sort(key=lambda x: x["code"])
    return universe


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-xlsx", action="store_true", help="cache/universe.xlsx から")
    ap.add_argument("--from-seed", action="store_true",
                    help="config/universe_seed.csv から（動作確認・約110社）")
    args = ap.parse_args()

    source = "xlsx" if args.from_xlsx else "seed" if args.from_seed else "jquants"
    universe = build(source)
    write_json(DATA / "universe.json", universe)
    by_sec: dict[str, int] = {}
    for r in universe:
        by_sec[r["sector33"]] = by_sec.get(r["sector33"], 0) + 1
    print(f"シクリカル・ユニバース {len(universe)} 社 → {DATA / 'universe.json'}")
    for s, n in sorted(by_sec.items(), key=lambda kv: -kv[1]):
        print(f"  {s}: {n}")
