"""1 銘柄の定量分析: 循環性 / トラフ / 生存力 / 正常化利益 / バリュエーション /
清算価値 / チェックリスト A・B・C / スコア。

入力: data/<code>/financials.json, prices.json, data/market/commodities.json, universe.json
出力: data/analysis/<code>.json
"""
from __future__ import annotations

import argparse

from common import (DATA, read_json, write_json, ols, pct_rank, median, stdev, cagr)

TAX = 0.30
MIDCYCLE_PER = 12.0

# asd.txt の換金率（清算価値）
LIQ_RATE = {"cash_deposits": 1.0, "receivables": 0.8, "inventories": 0.5,
            "ppe": 0.7, "intangibles": 0.0, "investments_other": 0.7}
DEBT_KEYS = ["short_loans", "current_lt_loans", "long_loans", "bonds",
             "current_bonds", "commercial_papers", "lease_current", "lease_noncurrent"]


def _col(annual: list[dict], key: str) -> list:
    return [r.get(key) for r in annual]


def _yoy(series: list) -> list:
    out = []
    for a, b in zip(series[:-1], series[1:]):
        out.append((b / a - 1) if (a and b and a != 0) else None)
    return out


def _mean(xs: list) -> float | None:
    v = [x for x in xs if x is not None]
    return sum(v) / len(v) if v else None


def _phase_score(commodities: list[str], market: dict) -> tuple[float | None, list]:
    """マップされた市況の平均フェーズ（谷寄り=1.0 / 中立=0.5 / 山寄り=0.0）。"""
    hint_val = {"谷寄り": 1.0, "中立": 0.5, "山寄り": 0.0}
    got = []
    for k in commodities:
        m = market.get(k) or {}
        h = m.get("phase_hint")
        if h in hint_val:
            got.append({"key": k, "label": m.get("label", k), "hint": h,
                        "pctile": m.get("pctile_15y"), "yoy": m.get("yoy"),
                        "stale": m.get("stale", False)})
    live = [g for g in got if not g["stale"] and g["hint"] in hint_val]
    score = _mean([hint_val[g["hint"]] for g in live]) if live else None
    return score, got


def analyze(code: str) -> dict | None:
    fin = read_json(DATA / code / "financials.json")
    if not fin or not fin.get("annual"):
        return None
    uni = {r["code"]: r for r in read_json(DATA / "universe.json", [])}.get(code, {})
    prices = read_json(DATA / code / "prices.json", {}) or {}
    market = read_json(DATA / "market" / "commodities.json", {}) or {}

    annual = sorted(fin["annual"], key=lambda r: r["fy"])
    fys = _col(annual, "fy")
    sales = _col(annual, "sales")
    net_income = _col(annual, "net_income")
    ordinary = _col(annual, "ordinary")
    profit_basis = "経常利益"
    if sum(o is not None for o in ordinary) < max(3, len(ordinary) // 2):
        for alt_key, label in (("operating", "営業利益"), ("net_income", "純利益")):
            alt = _col(annual, alt_key)
            if sum(o is not None for o in alt) >= max(3, len(alt) // 2):
                ordinary, profit_basis = alt, label
                break
    equity = _col(annual, "equity")
    equity_ratio = _col(annual, "equity_ratio")
    ocf = _col(annual, "ocf")
    bps = _col(annual, "bps")

    years_span = (fys[-1] - fys[0]) if len(fys) >= 2 else 0
    o_margin = [(o / s) if (o is not None and s) else None
                for o, s in zip(ordinary, sales)]

    # ---- コスト構造（回帰: 総費用 ≒ 売上 − 経常利益） -----------------
    xs, ys = [], []
    for s, o in zip(sales, ordinary):
        if s and o is not None:
            xs.append(s)
            ys.append(s - o)
    reg = ols(xs, ys)
    cost = {}
    if reg:
        a, b, r2 = reg
        b = max(0.0, min(1.2, b))
        cm = 1 - b
        latest_s, latest_o = sales[-1], ordinary[-1]
        cost = {
            "variable_cost_ratio": round(b, 4),
            "fixed_cost": round(a, 1),
            "contribution_margin": round(cm, 4),
            "breakeven_sales": round(a / cm, 1) if cm > 0.01 else None,
            "dol": (round(latest_s * cm / latest_o, 2)
                    if (latest_s and latest_o and latest_o > 0 and cm > 0) else None),
            "r2": round(r2, 3), "n_points": len(xs),
        }

    # ---- 循環性 -----------------------------------------------------
    s_yoy = [x for x in _yoy(sales) if x is not None]
    o_yoy = [x for x in _yoy(ordinary) if x is not None]
    elasticity = None
    if len(s_yoy) >= 3 and len(o_yoy) >= 3:
        sd_s, sd_o = stdev(s_yoy), stdev(o_yoy)
        if sd_s and sd_s > 0.01:
            elasticity = round(sd_o / sd_s, 2)
    margin_sd = stdev([m for m in o_margin if m is not None])
    med_margin = median([m for m in o_margin if m is not None])
    has_loss = any(o is not None and o < 0 for o in ordinary)
    has_margin_halving = bool(med_margin and any(
        m is not None and m < med_margin * 0.5 for m in o_margin))
    cyc_flags = [
        (elasticity or 0) >= 2.0,
        (margin_sd or 0) >= 0.03,
        has_loss,
        has_margin_halving,
        (cost.get("dol") or 0) >= 3.0,
    ]
    cyclicality_score = round(sum(cyc_flags) / len(cyc_flags), 2)

    # ---- トラフ判定（現在が谷か） --------------------------------------
    latest_margin = o_margin[-1]
    margin_pctile = pct_rank(latest_margin, [m for m in o_margin if m is not None])
    phase_score, phase_detail = _phase_score(uni.get("commodities", []), market)
    price_trough = None
    if prices.get("pctile_10y") is not None:
        price_trough = round((1 - prices["pctile_10y"]) * 0.5
                             + (prices.get("drawdown_from_peak_10y") or 0) * 0.5, 2)
    trough_parts = [
        (1 - margin_pctile) if margin_pctile is not None else None,
        1.0 if (latest_margin is not None and latest_margin < 0) else None,
        phase_score,
        price_trough,
    ]
    trough_score = _mean(trough_parts)

    # ---- 構造 vs 循環 ---------------------------------------------
    s_first = next((v for v in sales if v), None)
    s_last = next((v for v in reversed(sales) if v), None)
    sales_cagr = cagr(s_first, s_last, years_span) if years_span else None
    half = max(1, len(sales) // 2)
    peak_recent = max([v for v in sales[half:] if v] or [0])
    peak_earlier = max([v for v in sales[:half] if v] or [0])
    structural_ok = bool(
        peak_earlier and peak_recent >= peak_earlier * 0.9
        and (sales_cagr is None or sales_cagr > -0.02))
    structural_flag = (sales_cagr is not None and sales_cagr < -0.03)

    # ---- 生存力 -------------------------------------------------
    bs = fin.get("balance_sheet", {}) or {}
    shares = fin.get("shares_outstanding")
    if not shares and net_income and net_income[-1] and annual[-1].get("eps"):
        shares = net_income[-1] / annual[-1]["eps"]
    debt = sum(bs.get(k) or 0 for k in DEBT_KEYS)
    cash_bs = bs.get("cash_deposits") or annual[-1].get("cash") or 0
    latest_equity = next((v for v in reversed(equity) if v), None)
    net_debt = debt - cash_bs
    nd_to_equity = round(net_debt / latest_equity, 2) if latest_equity else None
    latest_er = next((v for v in reversed(equity_ratio) if v is not None), None)
    min_er = min([v for v in equity_ratio if v is not None] or [None])
    worst_loss = min([o for o in ordinary if o is not None and o < 0] or [0])
    survive_years = None
    if worst_loss < 0:
        survive_years = round((cash_bs + max(_mean(ocf) or 0, 0)) / abs(worst_loss), 1)
    survival_ok = bool(latest_er and latest_er >= 0.25
                       and (nd_to_equity is None or nd_to_equity <= 1.0))

    # ---- 正常化利益 & バリュエーション ------------------------------
    # ミッドサイクル売上 = 全期間の中央値（山谷を平均化）。ただし直近から乖離しすぎない範囲に。
    all_sales = [v for v in sales if v]
    norm_sales = median(all_sales) or s_last
    if s_last:
        norm_sales = max(min(norm_sales, s_last * 1.5), s_last * 0.6)
    norm_margin = med_margin
    norm_ordinary = (norm_sales * norm_margin
                     if (norm_sales and norm_margin is not None) else None)
    # コスト回帰が良好なときだけ、限界利益ベースの試算とブレンド
    if (norm_ordinary is not None and cost.get("r2", 0) >= 0.7
            and cost.get("fixed_cost", 0) > 0 and cost.get("contribution_margin")):
        alt = norm_sales * cost["contribution_margin"] - cost["fixed_cost"]
        norm_ordinary = (norm_ordinary + alt) / 2
    norm_net = norm_ordinary * (1 - TAX) if norm_ordinary is not None else None
    price = prices.get("latest")
    norm_eps = (norm_net / shares) if (norm_net is not None and shares) else None
    market_cap = price * shares if (price and shares) else None
    norm_per = (price / norm_eps) if (price and norm_eps and norm_eps > 0) else None
    fair_value = norm_eps * MIDCYCLE_PER if (norm_eps and norm_eps > 0) else None
    exp_return_x = (fair_value / price) if (fair_value and price) else None
    latest_bps = next((v for v in reversed(bps) if v), None)
    pbr = (price / latest_bps) if (price and latest_bps) else None

    # ---- 清算価値（下値メド） --------------------------------------
    liq = None
    if bs.get("total_liabilities"):
        adj_assets = sum((bs.get(k) or 0) * rate for k, rate in LIQ_RATE.items())
        liq = adj_assets - bs["total_liabilities"]
    liq_ps = (liq / shares) if (liq is not None and shares) else None
    downside_to_liq = ((price - liq_ps) / price
                       if (price and liq_ps is not None) else None)

    # ---- チェックリスト A/B/C -------------------------------------
    def mark(ok: bool | None, warn: bool = False) -> str:
        if ok:
            return "○"
        return "△" if warn else "×"

    checklist = {
        "A_cycle_not_structural": {
            "mark": mark(structural_ok, warn=not structural_flag),
            "note": (f"売上10年CAGR {sales_cagr:+.1%} / "
                     f"直近ピーク {'≥' if structural_ok else '<'} 過去ピーク"
                     if sales_cagr is not None else "売上履歴不足"),
        },
        "B_survive_to_next_peak": {
            "mark": mark(survival_ok, warn=bool(latest_er and latest_er >= 0.15)),
            "note": (f"自己資本比率 {latest_er:.0%}（最低 {min_er:.0%}） / "
                     f"ネットD/E {nd_to_equity}"
                     if latest_er is not None else "自己資本比率不明"),
        },
        "C_operating_leverage_upside": {
            "mark": mark(bool(cost.get("dol") and exp_return_x and exp_return_x >= 2),
                         warn=bool(exp_return_x and exp_return_x >= 1.5)),
            "note": (f"DOL {cost.get('dol')} / 期待リターン "
                     f"{exp_return_x:.1f}倍" if exp_return_x else "正常化利益を試算できず"),
        },
    }

    # ---- スコア（自動: 割安40 / 谷25 / 生存35） -----------------------
    def clamp01(x):
        return max(0.0, min(1.0, x))

    cheap_c = clamp01((exp_return_x - 1) / 2) if exp_return_x else (
        0.5 if (pbr and pbr < 1) else 0.2)
    trough_c = clamp01(trough_score) if trough_score is not None else 0.3
    surv_c = clamp01(
        (latest_er or 0) / 0.5 * 0.6
        + (1 - clamp01((nd_to_equity or 0) / 1.5)) * 0.4)
    auto_score = round(100 * (0.40 * cheap_c + 0.25 * trough_c + 0.35 * surv_c), 1)

    passes = {
        "s1_cheap": bool((pbr and pbr < 1.0) or (norm_per and norm_per < 8)
                         or (exp_return_x and exp_return_x >= 2)),
        "s2_cyclical": cyclicality_score >= 0.4,
        "s3_trough": bool((margin_pctile is not None and margin_pctile <= 0.4)
                          or (latest_margin is not None and latest_margin < 0)
                          or (phase_score is not None and phase_score >= 0.7)),
        "s4_structural_ok": structural_ok,
        "s5_survivable": survival_ok or bool(
            latest_er and latest_er >= 0.15
            and (nd_to_equity is None or nd_to_equity <= 1.6)),
    }
    passes["pass_all"] = bool(
        passes["s2_cyclical"] and passes["s3_trough"] and passes["s4_structural_ok"]
        and passes["s5_survivable"]
        and (passes["s1_cheap"] or (exp_return_x and exp_return_x >= 1.5)))

    out = {
        "code": code, "name": fin.get("name", ""), "sector33": uni.get("sector33", ""),
        "market": uni.get("market", ""), "profit_basis": profit_basis,
        "as_of_price": prices.get("as_of"), "price": price,
        "market_cap_oku": round(market_cap / 1e8, 1) if market_cap else None,
        "fy_range": [fys[0], fys[-1]] if fys else None, "n_years": len(fys),
        "series": {"fy": fys, "sales": sales, "ordinary": ordinary,
                   "ordinary_margin": [round(m, 4) if m is not None else None
                                       for m in o_margin],
                   "equity_ratio": equity_ratio, "ocf": ocf},
        "cost_structure": cost,
        "cyclicality": {"score": cyclicality_score, "elasticity": elasticity,
                        "margin_stdev": round(margin_sd, 4) if margin_sd else None,
                        "has_loss_year": has_loss, "median_margin": (
                            round(med_margin, 4) if med_margin is not None else None)},
        "trough": {"score": round(trough_score, 3) if trough_score is not None else None,
                   "latest_margin": (round(latest_margin, 4)
                                     if latest_margin is not None else None),
                   "margin_pctile": (round(margin_pctile, 3)
                                     if margin_pctile is not None else None),
                   "market_phase_score": (round(phase_score, 2)
                                          if phase_score is not None else None),
                   "market_phase_detail": phase_detail,
                   "price_pctile_10y": prices.get("pctile_10y"),
                   "price_drawdown_10y": prices.get("drawdown_from_peak_10y")},
        "structural": {"sales_cagr": round(sales_cagr, 4) if sales_cagr is not None else None,
                       "ok": structural_ok, "shrink_flag": structural_flag},
        "survival": {"ok": survival_ok, "equity_ratio": latest_er,
                     "min_equity_ratio": min_er, "net_debt": round(net_debt, 1),
                     "net_debt_to_equity": nd_to_equity,
                     "survive_years_if_loss": survive_years},
        "valuation": {"shares_outstanding": shares,
                      "normalized_sales": round(norm_sales, 1) if norm_sales else None,
                      "normalized_margin": round(norm_margin, 4) if norm_margin is not None else None,
                      "normalized_ordinary": round(norm_ordinary, 1) if norm_ordinary is not None else None,
                      "normalized_eps": round(norm_eps, 2) if norm_eps else None,
                      "normalized_per": round(norm_per, 1) if norm_per else None,
                      "midcycle_per": MIDCYCLE_PER,
                      "fair_value": round(fair_value, 1) if fair_value else None,
                      "expected_return_x": round(exp_return_x, 2) if exp_return_x else None,
                      "pbr": round(pbr, 2) if pbr else None},
        "liquidation": {"value": round(liq, 1) if liq is not None else None,
                        "per_share": round(liq_ps, 1) if liq_ps is not None else None,
                        "downside_to_liquidation": (round(downside_to_liq, 3)
                                                    if downside_to_liq is not None else None)},
        "checklist": checklist,
        "auto_score": auto_score,
        "passes": passes,
        "catalyst": {"note": "", "kpi": "", "manual_score": None},  # 手入力欄
        "phase_manual": {"note": ""},                               # 手入力欄
    }
    write_json(DATA / "analysis" / f"{code}.json", out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    args = ap.parse_args()
    for c in args.codes:
        r = analyze(c)
        if not r:
            print(f"{c}: 分析不可（財務データ不足）")
            continue
        v = r["valuation"]
        print(f"{c} {r['name']} [{r['sector33']}] "
              f"score={r['auto_score']} pass={r['passes']['pass_all']} "
              f"期待R={v['expected_return_x']}x PBR={v['pbr']} "
              f"正常化PER={v['normalized_per']} "
              f"A/B/C={''.join(r['checklist'][k]['mark'] for k in r['checklist'])}")
