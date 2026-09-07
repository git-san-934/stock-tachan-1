"""証券コードを1つ渡して、財務→株価→分析まで通す（動作確認用）。

  python scripts/run_pipeline.py 5401
"""
from __future__ import annotations

import argparse
import json

from fetch_financials import build as build_fin
from fetch_prices import build as build_prices
from analyze import analyze


def run(code: str) -> None:
    print(f"[1/3] 財務 (EDINET) …")
    build_fin(code)
    print(f"[2/3] 株価 (Yahoo) …")
    build_prices(code)
    print(f"[3/3] 分析 …")
    a = analyze(code)
    if not a:
        print("分析不可")
        return
    print(json.dumps({
        "code": a["code"], "name": a["name"], "sector33": a["sector33"],
        "auto_score": a["auto_score"], "passes": a["passes"],
        "valuation": a["valuation"], "checklist":
            {k: a["checklist"][k]["mark"] for k in a["checklist"]},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    args = ap.parse_args()
    run(args.code)
