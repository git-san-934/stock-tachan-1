"""シクリカルバリュー・スクリーナーの全体更新。

  python scripts/update_all.py                       # 標準（差分）
  python scripts/update_all.py --full                # 財務を全社取り直す
  python scripts/update_all.py --skip-index          # 有報索引の再収集を省く
  python scripts/update_all.py --skip-prices         # 株価取得を省く（CI 用）
  python scripts/update_all.py --limit 50            # 先頭50社だけ（動作確認）

途中で止めても、財務は data/<code>/financials.json 単位でスキップして再開できる。
CI では --skip-prices（Yahoo が 429 になりやすい）。株価はローカルで取ってコミットする。
"""
from __future__ import annotations

import argparse

from common import DATA, read_json
from fetch_financials import build as build_fin
import fetch_financials


def _load_index():
    from fetch_yuho_index import INDEX_FILE
    return read_json(INDEX_FILE, {}) or {}


def main(args) -> None:
    # 0) ユニバース
    if args.refresh_universe or not (DATA / "universe.json").exists():
        print("== ユニバース収集 ==")
        from fetch_universe import build as build_universe
        from common import write_json
        src = "xlsx" if args.universe_xlsx else "jquants"
        write_json(DATA / "universe.json", build_universe(src))

    universe = read_json(DATA / "universe.json", [])
    if args.limit:
        universe = universe[: args.limit]
    codes = [u["code"] for u in universe]
    print(f"ユニバース {len(codes)} 社")

    # 1) 有報索引
    if not args.skip_index:
        print("== 有報索引の収集（EDINET 書類一覧の走査）==")
        from fetch_yuho_index import harvest, INDEX_FILE
        from common import write_json
        idx = harvest(years=args.index_years, refresh=7)
        prev = read_json(INDEX_FILE, {}) or {}
        for c, rows in prev.items():
            have = {r["doc_id"] for r in idx.get(c, [])}
            idx[c] = sorted(idx.get(c, []) + [r for r in rows if r["doc_id"] not in have],
                            key=lambda r: r["period_end"] or r["submit"], reverse=True)
        write_json(INDEX_FILE, idx)
    fetch_financials.YUHO_INDEX = _load_index()

    # 2) 財務（既存かつ最新有報が変わっていなければスキップ）
    print("== 財務の取得（EDINET 有報 CSV）==")
    idx = fetch_financials.YUHO_INDEX
    done = fail = skip = 0
    for i, code in enumerate(codes, 1):
        fp = DATA / code / "financials.json"
        if not args.full and fp.exists():
            cur = read_json(fp, {})
            latest_in_index = (idx.get(code) or [{}])[0].get("doc_id")
            if not latest_in_index or cur.get("latest_doc_id") == latest_in_index:
                skip += 1
                continue
        try:
            r = build_fin(code)
            done += bool(r)
            fail += not r
        except Exception as err:  # noqa: BLE001
            print(f"  {code}: 失敗 {err}")
            fail += 1
        if i % 100 == 0:
            print(f"  [{i}/{len(codes)}] 取得 {done} / 既存 {skip} / 失敗 {fail}")
    print(f"財務: 取得 {done} / 既存スキップ {skip} / 失敗 {fail}")

    # 3) 株価
    if not args.skip_prices:
        print("== 株価の取得（Yahoo）==")
        from fetch_prices import build as build_prices
        for i, code in enumerate(codes, 1):
            build_prices(code, max_age_days=args.price_max_age)
            if i % 50 == 0:
                print(f"  [{i}/{len(codes)}]")

    # 4) 市況
    print("== 市況の取得（FRED）==")
    from fetch_market import build as build_market
    build_market()

    # 5) 集計
    print("== 分析・ランキング ==")
    from build_shortlist import run as build_shortlist
    build_shortlist(limit=args.limit)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="財務を全社取り直す")
    ap.add_argument("--skip-index", action="store_true")
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--universe-xlsx", action="store_true",
                    help="ユニバースを cache/universe.xlsx から作る")
    ap.add_argument("--index-years", type=int, default=6)
    ap.add_argument("--price-max-age", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    main(ap.parse_args())
