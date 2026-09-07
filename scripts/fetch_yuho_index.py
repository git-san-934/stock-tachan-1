"""EDINET の書類一覧を数年ぶんさかのぼり、有価証券報告書の索引を作る。

  python scripts/fetch_yuho_index.py [--years 6] [--refresh 7]

各日のレスポンスは edinet.py がキャッシュするので、2 回目以降は速い。
初回は years=6 で約 2,200 リクエスト（1 リクエスト 0.15 秒 sleep ＝ 6〜10 分）。

出力: cache/yuho_index.json
  { "5401": [ {"doc_id","period_start","period_end","submit","desc","consolidated"} ... 新しい順 ] }
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from common import CACHE, read_json, write_json, short_seccode
from edinet import get_doc_list, DOC_TYPE_YUHO

INDEX_FILE = CACHE / "yuho_index.json"


def harvest(years: int = 6, refresh: int = 7) -> dict[str, list[dict]]:
    today = date.today()
    days = int(years * 365.25) + 5
    by_code: dict[str, dict[str, dict]] = {}  # code -> {doc_id -> row}

    for offset in range(days + 1):
        d = (today - timedelta(days=offset)).isoformat()
        try:
            payload = get_doc_list(d, use_cache=offset >= refresh)
        except Exception as err:  # noqa: BLE001
            print(f"  {d}: 取得失敗 {err}")
            continue
        for row in payload.get("results") or []:
            if row.get("docTypeCode") != DOC_TYPE_YUHO:
                continue
            sec = (row.get("secCode") or "").strip()
            if not sec:
                continue
            code = short_seccode(sec)
            doc_id = row.get("docID")
            # 訂正有報（docDescription に「訂正」）は本表を持たないことが多い→除外
            desc = row.get("docDescription") or ""
            if "訂正" in desc:
                continue
            by_code.setdefault(code, {})[doc_id] = {
                "doc_id": doc_id,
                "period_start": row.get("periodStart") or "",
                "period_end": row.get("periodEnd") or "",
                "submit": row.get("submitDateTime") or "",
                "desc": desc,
            }
        if offset % 200 == 0:
            print(f"  ... {d} まで走査 / 収集 {len(by_code)} 社")

    index: dict[str, list[dict]] = {}
    for code, docs in by_code.items():
        rows = sorted(docs.values(), key=lambda r: r["period_end"] or r["submit"],
                      reverse=True)
        index[code] = rows
    return index


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--refresh", type=int, default=7)
    args = ap.parse_args()

    index = harvest(years=args.years, refresh=args.refresh)
    # 既存索引とマージ（過去に取れていた古い書類を失わない）
    prev = read_json(INDEX_FILE, {}) or {}
    for code, rows in prev.items():
        have = {r["doc_id"] for r in index.get(code, [])}
        merged = index.get(code, []) + [r for r in rows if r["doc_id"] not in have]
        merged.sort(key=lambda r: r["period_end"] or r["submit"], reverse=True)
        index[code] = merged

    write_json(INDEX_FILE, index)
    total_docs = sum(len(v) for v in index.values())
    print(f"有報索引: {len(index)} 社 / {total_docs} 書類 → {INDEX_FILE}")
