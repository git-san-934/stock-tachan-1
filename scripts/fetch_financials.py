"""1 銘柄の10年財務を EDINET 有報から組み立てる。

戦略: 「主要な経営指標等の推移」は 1 書類で5年ぶん入っている。最新有報と、
その約5年前の有報の2書類をダウンロードし、5年表を2枚マージして最大10年にする。
最新有報からは BS 明細（清算価値・有利子負債・現金）と発行済株式数も取る。

出力: data/<code>/financials.json
"""
from __future__ import annotations

import argparse

from common import DATA, read_json, write_json
from xbrl_csv import parse_doc, DUR_CONTEXTS, INST_CONTEXTS

YUHO_INDEX = None  # lazy

# ---- 主要な経営指標等の推移（連結優先）: 候補要素名 --------------------
E_SALES = ["NetSalesSummaryOfBusinessResults", "RevenueIFRSSummaryOfBusinessResults",
           "OperatingRevenue1SummaryOfBusinessResults",
           "NetSalesAndOperatingRevenue2SummaryOfBusinessResults",
           "OrdinaryRevenueBankingBusinessSummaryOfBusinessResults"]
E_ORDINARY = ["OrdinaryIncomeLossSummaryOfBusinessResults",
              "OrdinaryIncomeSummaryOfBusinessResults",
              "OrdinaryProfitSummaryOfBusinessResults",
              "OrdinaryProfitLossSummaryOfBusinessResults",
              "RecurringProfitSummaryOfBusinessResults",
              "ProfitLossBeforeTaxIFRSSummaryOfBusinessResults",
              "ProfitLossBeforeTaxSummaryOfBusinessResults",
              "ProfitBeforeTaxIFRSSummaryOfBusinessResults"]
E_NETINC = ["ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
            "NetIncomeLossSummaryOfBusinessResults",
            "ProfitAttributableToOwnersOfParentSummaryOfBusinessResults",
            "ProfitLossSummaryOfBusinessResults",
            "ProfitSummaryOfBusinessResults",
            "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults"]
E_EQUITY = ["NetAssetsSummaryOfBusinessResults",
            "EquityAttributableToOwnersOfParentIFRSSummaryOfBusinessResults",
            "TotalEquityIFRSSummaryOfBusinessResults"]
E_ASSETS = ["TotalAssetsSummaryOfBusinessResults",
            "TotalAssetsIFRSSummaryOfBusinessResults"]
E_EQRATIO = ["EquityToAssetRatioSummaryOfBusinessResults",
             "CapitalAdequacyRatioSummaryOfBusinessResults",
             "RatioOfOwnersEquityToGrossAssetsSummaryOfBusinessResults"]
E_ROE = ["RateOfReturnOnEquitySummaryOfBusinessResults",
         "NetIncomeLossToShareholdersEquityRatioSummaryOfBusinessResults"]
E_EPS = ["BasicEarningsLossPerShareSummaryOfBusinessResults",
         "BasicEarningsPerShareSummaryOfBusinessResults",
         "NetIncomeLossPerShareSummaryOfBusinessResults",
         "EarningsPerShareSummaryOfBusinessResults",
         "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults"]
E_BPS = ["NetAssetsPerShareSummaryOfBusinessResults",
         "EquityToAssetsPerShareIFRSSummaryOfBusinessResults"]
E_OCF = ["NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
         "CashFlowsFromOperatingActivitiesSummaryOfBusinessResults"]
E_CASH = ["CashAndCashEquivalentsSummaryOfBusinessResults",
          "CashAndCashEquivalentsAtEndOfPeriodSummaryOfBusinessResults"]
E_SHARES = ["NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStockSummaryOfBusinessResults",
            "TotalNumberOfIssuedSharesSummaryOfBusinessResults"]

E_OPERATING = ["OperatingIncomeSummaryOfBusinessResults",
               "OperatingIncomeLossSummaryOfBusinessResults",
               "OperatingProfitSummaryOfBusinessResults",
               "OperatingProfitLossSummaryOfBusinessResults",
               "OperatingProfitLossIFRSSummaryOfBusinessResults",
               "OperatingIncomeLossIFRSSummaryOfBusinessResults"]

SUMMARY_FIELDS = {
    "sales": E_SALES, "ordinary": E_ORDINARY, "operating": E_OPERATING,
    "net_income": E_NETINC,
    "equity": E_EQUITY, "assets": E_ASSETS, "equity_ratio": E_EQRATIO,
    "roe": E_ROE, "eps": E_EPS, "bps": E_BPS, "ocf": E_OCF, "cash": E_CASH,
}

# ---- BS 明細（jppfs_cor, 最新有報の CurrentYearInstant）----------------
E_BS = {
    "cash_deposits": ["CashAndDeposits"],
    "receivables": ["NotesAndAccountsReceivableTrade",
                    "NotesAndAccountsReceivableTradeAndContractAssets",
                    "TradeAndOtherReceivablesIFRS"],
    "inventories": ["Inventories", "MerchandiseAndFinishedGoods"],
    "ppe": ["PropertyPlantAndEquipment", "PropertyPlantAndEquipmentIFRS"],
    "intangibles": ["IntangibleAssets", "IntangibleAssetsIFRS", "Goodwill"],
    "investments_other": ["InvestmentsAndOtherAssets"],
    "total_assets": ["Assets", "TotalAssetsIFRS"],
    "total_liabilities": ["Liabilities", "TotalLiabilitiesIFRS"],
    "net_assets_bs": ["NetAssets", "EquityIFRS"],
    "short_loans": ["ShortTermLoansPayable"],
    "current_lt_loans": ["CurrentPortionOfLongTermLoansPayable"],
    "long_loans": ["LongTermLoansPayable"],
    "bonds": ["BondsPayable"],
    "current_bonds": ["CurrentPortionOfBondsPayable", "CurrentPortionOfBonds"],
    "commercial_papers": ["CommercialPapersLiabilities", "CommercialPapers"],
    "lease_current": ["LeaseObligationsCurrent", "LeaseLiabilitiesCurrentIFRS"],
    "lease_noncurrent": ["LeaseObligationsNoncurrent", "LeaseLiabilitiesNoncurrentIFRS"],
}


def _norm_ratio(v):
    if v is None:
        return None
    return v / 100 if abs(v) > 1.5 else v


def _fy(period_end: str) -> int | None:
    try:
        return int(period_end[:4])
    except (ValueError, TypeError):
        return None


def _pick_docs(code: str) -> list[dict]:
    global YUHO_INDEX
    if YUHO_INDEX is None:
        from fetch_yuho_index import INDEX_FILE
        YUHO_INDEX = read_json(INDEX_FILE, {}) or {}
    docs = YUHO_INDEX.get(code, [])
    if not docs:
        return []
    latest = docs[0]
    picked = [latest]
    target_fy = (_fy(latest["period_end"]) or 0) - 5
    older = [d for d in docs[1:] if _fy(d["period_end"])]
    if older:
        best = min(older, key=lambda d: abs((_fy(d["period_end"]) or 0) - target_fy))
        if best["doc_id"] != latest["doc_id"]:
            picked.append(best)
    return picked


def build(code: str) -> dict | None:
    picked = _pick_docs(code)
    if not picked:
        print(f"  {code}: 有報索引に無し")
        return None

    years: dict[int, dict] = {}
    meta: dict = {}
    bs: dict = {}
    shares = None

    for i, d in enumerate(picked):
        try:
            doc = parse_doc(d["doc_id"])
        except Exception as err:  # noqa: BLE001
            print(f"  {code}: {d['doc_id']} パース失敗 {err}")
            continue
        base_fy = _fy(doc.meta.get("period_end") or d["period_end"])
        if base_fy is None:
            continue
        if i == 0:
            meta = dict(doc.meta)
            shares = doc.num(E_SHARES, "CurrentYearInstant") or \
                doc.num(E_SHARES, "CurrentYearDuration")
            for k, names in E_BS.items():
                bs[k] = doc.num(names, "CurrentYearInstant")

        for j in range(5):  # CurrentYear..Prior4Year
            fy = base_fy - j
            rec = years.setdefault(fy, {})
            for field, names in SUMMARY_FIELDS.items():
                inst = field in ("equity", "assets", "cash", "bps", "equity_ratio")
                ctx = (INST_CONTEXTS if inst else DUR_CONTEXTS)[j]
                v = doc.num(names, ctx)
                if v is None:
                    continue
                if field in ("equity_ratio", "roe"):
                    v = _norm_ratio(v)
                # 最新書類（i==0）を優先。既存が最新由来なら上書きしない
                if field not in rec or i == 0:
                    rec[field] = v

    series = [dict(fy=fy, **years[fy]) for fy in sorted(years) if years[fy]]
    if not series:
        print(f"  {code}: 数値が取れず")
        return None

    out = {
        "code": code,
        "name": meta.get("filer_name", ""),
        "edinet_code": meta.get("edinet_code", ""),
        "latest_doc_id": picked[0]["doc_id"],
        "latest_period_end": meta.get("period_end", picked[0]["period_end"]),
        "shares_outstanding": shares,
        "annual": series,
        "balance_sheet": bs,
        "source_docs": [d["doc_id"] for d in picked],
    }
    write_json(DATA / code / "financials.json", out)
    n = len(series)
    print(f"  {code} {out['name']}: {n}年 "
          f"({series[0]['fy']}–{series[-1]['fy']}) shares={shares}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+", help="証券コード（4桁）")
    args = ap.parse_args()
    for c in args.codes:
        build(c)
