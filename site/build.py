"""静的サイト生成: docs/index.html（ランキング）と docs/company/<code>.html（詳細）。

  python site/build.py
  python -m http.server -d docs 8000   # ローカル確認

LLM もサーバーも使わない。data/ の JSON を読んで HTML を書くだけ。
"""
from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

FUNNEL_LABELS = ["⓪規模", "①割安", "②循環性", "③谷", "④非衰退", "⑤生存力", "⑥上値"]

CSS = """
:root{--bg:#f7f5f0;--card:#fff;--text:#23201b;--sub:#6b645a;--border:#e5e0d6;
--accent:#c8502d;--ok:#2e7d5b;--warn:#b7791f;--ng:#b23b3b;--head:#efe9dd}
@media(prefers-color-scheme:dark){:root{--bg:#1c1a17;--card:#262320;--text:#f0ece4;
--sub:#a89f92;--border:#38342e;--accent:#e0662f;--ok:#4caf87;--warn:#d9a441;
--ng:#e07a7a;--head:#2f2b26}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;padding:0;background:var(--bg);color:var(--text);line-height:1.6;
font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif}
a{color:var(--accent)}
.wrap{max-width:1200px;margin:0 auto;padding:1.5rem 1rem 4rem}
h1{font-size:1.4rem;margin:.2rem 0}
h2{font-size:1.05rem;margin:1.8rem 0 .6rem;border-left:4px solid var(--accent);padding-left:.5rem}
.muted{color:var(--sub);font-size:.85rem}
.controls{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin:1rem 0}
select,input{font:inherit;padding:.35rem .5rem;background:var(--card);color:var(--text);
border:1px solid var(--border);border-radius:.4rem}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:.6rem}
table{border-collapse:collapse;width:100%;font-size:.85rem;min-width:900px}
th,td{padding:.45rem .55rem;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
th{background:var(--head);position:sticky;top:0;cursor:pointer;font-weight:600}
td.l,th.l{text-align:left}
tbody tr:hover{background:var(--head)}
.pill{display:inline-block;min-width:1.3em;text-align:center;border-radius:.3rem;
padding:0 .25rem;font-size:.78rem}
.f1{background:var(--ok);color:#fff}.f0{background:var(--border);color:var(--sub)}
.mk{font-weight:700}.mk.○{color:var(--ok)}.mk.△{color:var(--warn)}.mk.×{color:var(--ng)}
.badge{display:inline-block;background:var(--ok);color:#fff;border-radius:.3rem;
padding:0 .4rem;font-size:.75rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:.6rem;
padding:1rem 1.1rem;margin:.8rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.6rem 1.2rem}
.kv{font-size:.9rem}.kv b{display:block;color:var(--sub);font-weight:400;font-size:.78rem}
.note{font-size:.85rem;color:var(--sub)}
textarea{width:100%;font:inherit;padding:.5rem;background:var(--bg);color:var(--text);
border:1px solid var(--border);border-radius:.4rem;min-height:4.5rem}
svg{max-width:100%;height:auto}
.legend{font-size:.78rem;color:var(--sub);display:flex;gap:1rem;flex-wrap:wrap;margin:.3rem 0}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def fmt(v, pct=False, x=False, digits=1):
    if v is None:
        return "—"
    if pct:
        return f"{v*100:.{digits}f}%"
    if x:
        return f"{v:.2f}×"
    if isinstance(v, float):
        return f"{v:,.{digits}f}"
    return f"{v:,}"


def oku(v):
    """円 → 億円 表示。"""
    if v is None:
        return "—"
    return f"{v/1e8:,.0f} 億円"


# ------------------------------------------------------------------ charts

def bar_line_chart(fy, sales, ordinary, margin) -> str:
    """売上=棒 / 経常利益=棒(色分け) / 経常利益率=折れ線。単純な自前 SVG。"""
    pts = [(f, s, o, m) for f, s, o, m in zip(fy, sales, ordinary, margin)]
    pts = [p for p in pts if p[1] is not None]
    if len(pts) < 2:
        return "<p class='note'>チャートを描くデータが足りません。</p>"
    W, H, pad = 720, 240, 34
    smax = max(p[1] for p in pts) or 1
    omin = min([p[2] for p in pts if p[2] is not None] or [0])
    omax = max([p[2] for p in pts if p[2] is not None] or [1])
    omin = min(omin, 0)
    n = len(pts)
    bw = (W - 2 * pad) / n
    def x(i): return pad + bw * (i + 0.5)
    def ysales(v): return H - pad - (v / smax) * (H - 2 * pad) * 0.6
    def yo(v):
        rng = (omax - omin) or 1
        return H - pad - ((v - omin) / rng) * (H - 2 * pad)
    parts = [f"<svg viewBox='0 0 {W} {H}' role='img'>"]
    parts.append(f"<line x1='{pad}' y1='{H-pad}' x2='{W-pad}' y2='{H-pad}' stroke='var(--border)'/>")
    if omin < 0:
        zy = yo(0)
        parts.append(f"<line x1='{pad}' y1='{zy:.1f}' x2='{W-pad}' y2='{zy:.1f}' stroke='var(--border)' stroke-dasharray='3 3'/>")
    for i, (f, s, o, m) in enumerate(pts):
        sh = (s / smax) * (H - 2 * pad) * 0.6
        parts.append(f"<rect x='{x(i)-bw*0.32:.1f}' y='{H-pad-sh:.1f}' width='{bw*0.64:.1f}' "
                     f"height='{sh:.1f}' fill='var(--border)'/>")
        if o is not None:
            oy = yo(o); zy = yo(0)
            col = "var(--ok)" if o >= 0 else "var(--ng)"
            parts.append(f"<rect x='{x(i)-bw*0.16:.1f}' y='{min(oy,zy):.1f}' width='{bw*0.32:.1f}' "
                         f"height='{abs(oy-zy):.1f}' fill='{col}'/>")
        parts.append(f"<text x='{x(i):.1f}' y='{H-pad+14}' font-size='10' fill='var(--sub)' "
                     f"text-anchor='middle'>{f}</text>")
    # 経常利益率（%）を上部バンドに折れ線で
    ms = [p[3] for p in pts if p[3] is not None]
    if len(ms) >= 2:
        mlo, mhi = min(ms + [0]), max(ms + [0.01])
        rng = (mhi - mlo) or 1
        def ym(v): return pad + (1 - (v - mlo) / rng) * (H - 2 * pad) * 0.42
        mline = [(x(i), ym(pts[i][3])) for i in range(n) if pts[i][3] is not None]
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in mline)
        parts.append(f"<path d='{d}' fill='none' stroke='var(--accent)' stroke-width='2'/>")
        for i in range(n):
            if pts[i][3] is not None:
                parts.append(f"<text x='{x(i):.1f}' y='{ym(pts[i][3])-5:.1f}' font-size='9' "
                             f"fill='var(--accent)' text-anchor='middle'>{pts[i][3]*100:.0f}%</text>")
    parts.append("</svg>")
    return "".join(parts)


def spark(series, pctile=None) -> str:
    v = [p for p in series if p is not None]
    if len(v) < 2:
        return ""
    W, H = 160, 36
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1
    step = W / (len(v) - 1)
    d = "M" + " L".join(f"{i*step:.1f},{H-2-(x-lo)/rng*(H-4):.1f}" for i, x in enumerate(v))
    dot = f"<circle cx='{W:.1f}' cy='{H-2-(v[-1]-lo)/rng*(H-4):.1f}' r='2.5' fill='var(--accent)'/>"
    return f"<svg viewBox='0 0 {W} {H}'><path d='{d}' fill='none' stroke='var(--sub)' stroke-width='1.5'/>{dot}</svg>"


def cycle_wave(cur: int) -> str:
    """株価循環の波（① 谷 → ⑤ 山 → ⑧ 谷）。現在局面 cur を大きく表示。"""
    import math
    W, H, pad = 560, 150, 28
    amp = (H - 2 * pad) / 2
    mid = H / 2

    def ang(n): return math.radians(270 + (n - 1) * 45)
    def X(n): return pad + (n - 1) / 8 * (W - 2 * pad)
    def Y(n): return mid - amp * math.sin(ang(n))

    pts = []
    for t in range(129):
        n = 1 + t / 16
        pts.append(f"{X(n):.1f},{Y(n):.1f}")
    d = "M" + " L".join(pts)
    out = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='株価循環での現在位置'>"]
    out.append(f"<rect x='0' y='0' width='{X(2.5):.0f}' height='{H}' fill='var(--ok)' opacity='0.09'/>")
    out.append(f"<rect x='{X(6.5):.0f}' y='0' width='{W - X(6.5):.0f}' height='{H}' fill='var(--ok)' opacity='0.09'/>")
    out.append(f"<rect x='{X(3.5):.0f}' y='0' width='{X(6.5) - X(3.5):.0f}' height='{H}' fill='var(--warn)' opacity='0.09'/>")
    out.append(f"<path d='{d}' fill='none' stroke='var(--border)' stroke-width='2'/>")
    for i, c in enumerate("①②③④⑤⑥⑦⑧"):
        n = i + 1
        on = n == cur
        up = 3 <= n <= 6
        col = "var(--accent)" if on else "var(--sub)"
        out.append(f"<circle cx='{X(n):.1f}' cy='{Y(n):.1f}' r='{7 if on else 3.4}' "
                   f"fill='{'var(--accent)' if on else 'var(--sub)'}'/>")
        out.append(f"<text x='{X(n):.1f}' y='{Y(n) + (-11 if up else 19):.1f}' font-size='11' "
                   f"text-anchor='middle' font-weight='{700 if on else 400}' fill='{col}'>{c}</text>")
        if on:
            out.append(f"<text x='{X(n):.1f}' y='{Y(n) + (-25 if up else 33):.1f}' font-size='10' "
                       f"text-anchor='middle' fill='var(--accent)'>いまここ</text>")
    out.append(f"<text x='{X(1.6):.0f}' y='{H - 5}' font-size='9' fill='var(--ok)' text-anchor='middle'>谷ゾーン（買い場）</text>")
    out.append(f"<text x='{X(5):.0f}' y='12' font-size='9' fill='var(--warn)' text-anchor='middle'>山ゾーン（売り場）</text>")
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ pages

def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">
<p class="muted"><a href="{up}index.html">← 一覧</a> ·
<a href="https://git-san-934.github.io/portal/">ポータル</a></p>
{body}
<footer class="muted" style="margin-top:3rem">
シクリカルバリュー・スクリーナー / 出典: EDINET 有価証券報告書・Yahoo Finance・FRED。
投資判断は自己責任で。数値は自動抽出のため誤りを含みます。
</footer></div></body></html>"""


def build_index(shortlist: dict) -> str:
    rows = shortlist["rows"]
    sectors = sorted({r["sector33"] for r in rows})
    opts = "".join(f"<option>{esc(s)}</option>" for s in sectors)
    data_json = json.dumps(rows, ensure_ascii=False)
    st = shortlist["stats"]
    body = f"""
<h1>シクリカルバリュー・スクリーナー</h1>
<p class="muted">生成 {esc(shortlist['generated'])} ／ 分析 {st['analyzed']} 社 ／
ふるい通過 <span class="badge">{st['pass_all']}</span> 社
（東証33業種のうちシクリカル業種{'・パイロット版' if st['analyzed'] < 300 else ''}）</p>
<p class="note">景気循環業界で「循環の谷」にいて、次の山まで生き残れて、
山で大きく跳ねる可能性がある割安株を機械的に絞り込む。手法は
<a href="https://git-san-934.github.io/portal/">ポータル</a>の投資ノート参照。
ふるい: ⓪規模（時価総額100億円以上）①割安 ②循環性 ③谷
④非衰退（構造縮小でない）⑤生存力 ⑥上値（正常化利益で期待リターン≥1倍）。</p>

<div class="controls">
<label><input type="checkbox" id="onlypass" checked> ふるい通過のみ</label>
<select id="sector"><option value="">業種すべて</option>{opts}</select>
<input id="q" placeholder="コード / 銘柄名で絞り込み" size="18">
<span class="muted" id="count"></span>
</div>

<div class="tablewrap"><table id="t"><thead><tr>
<th class="l" data-k="code">コード</th>
<th class="l" data-k="name">銘柄</th>
<th class="l" data-k="sector33">業種</th>
<th data-k="market_cap_oku">時価総額<br>(億円)</th>
<th data-k="auto_score">自動<br>スコア</th>
<th data-k="_funnel">ふるい</th>
<th data-k="expected_return_x">期待<br>リターン</th>
<th data-k="normalized_per" title="平常時（山谷ならし）の1株利益で見たPER">平常時<br>PER</th>
<th data-k="pbr" title="株価 ÷ 1株純資産">PBR</th>
<th data-k="cyclicality" title="景気にどれだけ振り回されるか">景気<br>敏感度</th>
<th data-k="trough_score" title="高いほど「いま谷にいる」度合いが強い">谷<br>サイン</th>
<th data-k="market_phase_score">市況<br>フェーズ</th>
<th data-k="_cycle">循環<br>局面</th>
<th data-k="equity_ratio">自己資本<br>比率</th>
<th data-k="net_debt_to_equity">ネット<br>D/E</th>
<th data-k="_abc">A/B/C</th>
</tr></thead><tbody></tbody></table></div>

<section style="margin-top:1.6rem">
<h2>循環局面の見かた（① 底入れ 〜 ⑧ 夜明け前）</h2>
<p class="note">シクリカルバリュー投資の株価循環を、各銘柄の<b>水準</b>（利益率・市況・株価が
過去のどの高さか）×<b>方向</b>（売上・利益率・市況の前年比）から自動で推定したもの。
<b>あくまで目安</b>。実際の局面は有報・在庫循環・市況スプレッド・先物カーブで確認すること。</p>
<div class="tablewrap"><table style="min-width:0;font-size:.85rem">
<thead><tr><th class="l">局面</th><th>売上</th><th>数量</th><th>価格</th>
<th class="l">状況</th><th>目安</th></tr></thead><tbody>
<tr><td class="l"><span class="mk ○">① 底入れ</span></td><td>→</td><td>→</td><td>→</td><td class="l">景気の底。動き出しを待つ</td><td>買い場</td></tr>
<tr><td class="l"><span class="mk ○">② 回復</span></td><td>↑</td><td>↑</td><td>→</td><td class="l">数量から回復が始まる</td><td>買い場</td></tr>
<tr><td class="l"><span class="mk △">③ 拡大</span></td><td>↑</td><td>↑</td><td>↑</td><td class="l">数量も価格も伸びる</td><td>保有</td></tr>
<tr><td class="l"><span class="mk ×">④ 過熱</span></td><td>↑</td><td>→</td><td>↑</td><td class="l">価格高騰で数量の伸びが鈍る</td><td>売り場</td></tr>
<tr><td class="l"><span class="mk ×">⑤ 高原</span></td><td>↑</td><td>→</td><td>↓</td><td class="l">価格が天井を打つ</td><td>売り場</td></tr>
<tr><td class="l"><span class="mk ×">⑥ 後退</span></td><td>↓</td><td>→</td><td>↓</td><td class="l">売上が減り始める</td><td>売り場</td></tr>
<tr><td class="l"><span class="mk ○">⑦ 不況</span></td><td>↓</td><td>↓</td><td>↓</td><td class="l">すべてが縮む（谷。下落途中）</td><td>まだ待つ</td></tr>
<tr><td class="l"><span class="mk ○">⑧ 夜明け前</span></td><td>→</td><td>→</td><td>↓</td><td class="l">安すぎて買い手がつき始める</td><td>買い場</td></tr>
</tbody></table></div>
</section>

<script>
const ROWS={data_json};
const FL={json.dumps(FUNNEL_LABELS,ensure_ascii=False)};
let sortK="auto_score",sortDir=-1;
const tb=document.querySelector("#t tbody");
const pct=v=>v==null?"—":(v*100).toFixed(0)+"%";
const num=(v,d=1)=>v==null?"—":Number(v).toLocaleString(undefined,{{maximumFractionDigits:d}});
function funnelCells(f){{return f.map((b,i)=>`<span class="pill ${{b?'f1':'f0'}}" title="${{FL[i]}}">${{b?'✓':'·'}}</span>`).join('')}}
function phase(v){{if(v==null)return"—";if(v>=0.7)return"谷寄り "+pct(v);if(v<=0.4)return"山寄り "+pct(v);return"中立 "+pct(v)}}
function cyc(cp){{if(!cp)return"—";const c=cp.zone==="buy"?"var(--ok)":cp.zone==="sell"?"var(--ng)":"var(--sub)";return`<span style="color:${{c}};font-weight:600">${{cp.label}}</span>`}}
function render(){{
 const onlyp=document.querySelector("#onlypass").checked;
 const sec=document.querySelector("#sector").value;
 const q=document.querySelector("#q").value.trim().toLowerCase();
 let rows=ROWS.filter(r=>(!onlyp||r.pass_all)&&(!sec||r.sector33===sec)&&
   (!q||r.code.toLowerCase().includes(q)||(r.name||"").toLowerCase().includes(q)));
 rows.sort((a,b)=>{{let x=a[sortK],y=b[sortK];
   if(sortK==="_funnel"){{x=a.funnel.filter(Boolean).length;y=b.funnel.filter(Boolean).length}}
   if(sortK==="_cycle"){{x=a.cycle_phase?a.cycle_phase.num:99;y=b.cycle_phase?b.cycle_phase.num:99}}
   x=x==null?-1e9:x;y=y==null?-1e9:y;return (x<y?-1:x>y?1:0)*sortDir}});
 document.querySelector("#count").textContent=rows.length+" 社";
 tb.innerHTML=rows.map(r=>`<tr>
 <td class="l"><a href="company/${{r.code}}.html">${{r.code}}</a></td>
 <td class="l">${{r.name||""}}</td>
 <td class="l">${{r.sector33||""}}</td>
 <td>${{num(r.market_cap_oku)}}</td>
 <td><b>${{num(r.auto_score)}}</b></td>
 <td>${{funnelCells(r.funnel)}}</td>
 <td>${{r.expected_return_x==null?"—":r.expected_return_x.toFixed(2)+"×"}}</td>
 <td>${{num(r.normalized_per)}}</td>
 <td>${{num(r.pbr,2)}}</td>
 <td>${{pct(r.cyclicality)}}</td>
 <td>${{pct(r.trough_score)}}</td>
 <td>${{phase(r.market_phase_score)}}</td>
 <td>${{cyc(r.cycle_phase)}}</td>
 <td>${{pct(r.equity_ratio)}}</td>
 <td>${{num(r.net_debt_to_equity,2)}}</td>
 <td>${{["A_cycle_not_structural","B_survive_to_next_peak","C_operating_leverage_upside"]
   .map(k=>`<span class="mk ${{r.checklist[k]}}">${{r.checklist[k]}}</span>`).join(" ")}}</td>
 </tr>`).join("");
}}
document.querySelectorAll("#t th").forEach(th=>th.onclick=()=>{{
 const k=th.dataset.k;if(!k)return;
 if(k===sortK)sortDir*=-1;else{{sortK=k;sortDir=(k==="code"||k==="name"||k==="sector33")?1:-1}}
 render();
}});
["onlypass","sector","q"].forEach(id=>document.querySelector("#"+id).addEventListener("input",render));
render();
</script>
"""
    return page("シクリカルバリュー・スクリーナー", body)


def kv(label: str, value: str) -> str:
    return f'<div class="kv"><b>{esc(label)}</b>{value}</div>'


def build_company(a: dict, market: dict) -> str:
    s = a["series"]
    v, t, sv, st_, liq = (a["valuation"], a["trough"], a["survival"],
                          a["structural"], a["liquidation"])
    cs = a["cost_structure"]
    chart = bar_line_chart(s["fy"], s["sales"], s["ordinary"], s["ordinary_margin"])

    phase_rows = "".join(
        f"<tr><td class='l'>{esc(d['label'])}</td><td>{esc(d['hint'])}</td>"
        f"<td>{fmt(d.get('pctile'),pct=True,digits=0)}</td>"
        f"<td>{fmt(d.get('yoy'),pct=True,digits=0)}</td>"
        f"<td>{'（古い）' if d.get('stale') else ''}</td></tr>"
        for d in t.get("market_phase_detail", []))

    def mk(key):
        c = a["checklist"][key]
        crit = (f"<div class='note' style='margin:.15rem 0'><b>{esc(c['criteria'])}</b></div>"
                if c.get("criteria") else "")
        return (f"<div class='card'><b class='mk {c['mark']}'>{c['mark']}</b> "
                f"{esc(_CHECK_TITLE[key])}{crit}"
                f"<div class='note'>{esc(c['note'])}</div></div>")

    cp = a.get("cycle_phase")
    cycle_block = ""
    if cp:
        col = {"buy": "var(--ok)", "sell": "var(--ng)"}.get(cp["zone"], "var(--sub)")
        zone_txt = {"buy": "買い場ゾーン", "sell": "売り場ゾーン"}.get(cp["zone"], "保有ゾーン")
        cycle_block = f"""<h2>いま循環のどこにいるか（推定）</h2>
<div class="card">
<p><b style="font-size:1.3rem;color:{col}">{esc(cp['label'])}</b>
<span class="note">（{zone_txt}）</span></p>
{cycle_wave(cp['num'])}
<div class="grid" style="margin-top:.5rem">
{kv("いまの高さ（0%=谷 / 100%=山）", fmt(cp['level'], pct=True, digits=0))}
{kv("向き（マイナス=下降 / プラス=上昇）", fmt(cp['momentum'], digits=2))}
</div>
<p class="note">「高さ」＝利益率・市況・株価がそれぞれ過去のどのあたりの水準かの平均。
「向き」＝売上・利益率・市況が前年比で上がっているか下がっているか。
<b>自動推定の目安</b>。実際の局面は在庫の増減・市況スプレッド・先物カーブで
確認すること（8局面の意味は<a href="../index.html">一覧ページ下部の凡例</a>）。</p>
</div>"""

    body = f"""
<h1>{esc(a['code'])} {esc(a['name'])}
{"<span class='badge'>ふるい通過</span>" if a['passes']['pass_all'] else ""}</h1>
<p class="muted">{esc(a['sector33'])}{(' · ' + esc(a['market'])) if a.get('market') else ''} ·
株価 {fmt(a['price'])} 円（{esc(a['as_of_price'])}） ·
時価総額 {fmt(a['market_cap_oku'])} 億円 ·
決算 {esc(a['fy_range'][0]) if a['fy_range'] else '?'}–{esc(a['fy_range'][1]) if a['fy_range'] else '?'}
（{a['n_years']}年） · 自動スコア <b>{fmt(a['auto_score'])}</b></p>

<h2>売上高・{esc(a.get('profit_basis','経常利益'))}・利益率（{a['n_years']}年）</h2>
<div class="card">{chart}
<div class="legend"><span>■ 売上高（灰）</span><span>■ 経常利益（緑=黒字 / 赤=赤字）</span>
<span>— 経常利益率（橙・上部）</span></div></div>

<h2>コスト構造（総費用≒売上−経常利益 を売上に回帰）</h2>
<div class="card"><div class="grid">
{kv("変動費率", fmt(cs.get('variable_cost_ratio'), pct=True))}
{kv("固定費（推定）", oku(cs.get('fixed_cost')))}
{kv("限界利益率", fmt(cs.get('contribution_margin'), pct=True))}
{kv("損益分岐点売上", oku(cs.get('breakeven_sales')))}
{kv("営業レバレッジ DOL", fmt(cs.get('dol')))}
{kv("回帰の当てはまり R²", fmt(cs.get('r2'), digits=2))}
</div><p class="note">DOL が高いほど、売上の変化に対して利益が大きく振れる（谷で赤字・山で急拡大）。</p></div>

<h2>景気にどれだけ振り回されるか（循環性）</h2>
<div class="card"><div class="grid">
{kv("景気敏感度スコア", fmt(a['cyclicality']['score'], pct=True))}
{kv("利益の振れ幅 ÷ 売上の振れ幅", fmt(a['cyclicality']['elasticity']))}
{kv("利益率のブレ幅", fmt(a['cyclicality']['margin_stdev'], pct=True))}
{kv("過去10年に赤字の年", "あり" if a['cyclicality']['has_loss_year'] else "なし")}
{kv("平常時の利益率（10年の中央値）", fmt(a['cyclicality']['median_margin'], pct=True))}
</div><p class="note">「利益の振れ幅 ÷ 売上の振れ幅」が大きいほど、売上が少し動くだけで
利益が大きく振れる＝景気に敏感な会社。</p></div>

<h2>いま循環の谷にいるか</h2>
<div class="card"><div class="grid">
{kv("谷サイン（総合・高いほど谷）", fmt(t['score'], pct=True))}
{kv("直近の利益率", fmt(t['latest_margin'], pct=True))}
{kv("利益率の位置（0%=10年で最低 / 100%=最高）", fmt(t['margin_pctile'], pct=True))}
{kv("市況の位置（1=谷 / 0=山）", fmt(t['market_phase_score']))}
{kv("株価の位置（0%=10年で最安 / 100%=最高値）", fmt(t['price_pctile_10y'], pct=True))}
{kv("10年高値からの下落率", fmt(t['price_drawdown_10y'], pct=True))}
</div>
{"<table style='margin-top:.6rem'><thead><tr><th class='l'>市況</th><th>フェーズ</th><th>15年での位置</th><th>前年比</th><th></th></tr></thead><tbody>"+phase_rows+"</tbody></table>" if phase_rows else "<p class='note'>この業種に紐づく自動取得の市況シリーズはありません。</p>"}
</div>
{cycle_block}

<h2>「谷」なのか「構造的な衰退」なのか</h2>
<div class="card"><div class="grid">
{kv("売上の10年成長率（年率）", fmt(st_['sales_cagr'], pct=True))}
{kv("判定", "循環の範囲内（戻れる見込み）" if st_['ok'] else "要注意")}
{kv("構造縮小の疑い", "⚠ あり" if st_['shrink_flag'] else "なし")}
</div><p class="note">売上が山谷を繰り返しつつ長期で減っていなければ「循環の谷」。
EV化・脱炭素・デジタル代替・中国の恒常的な過剰供給などで市場そのものが
縮小していないかは、数値だけでなく目で確認する。</p></div>

<h2>次の山まで生き残れるか</h2>
<div class="card"><div class="grid">
{kv("自己資本比率（直近）", fmt(sv['equity_ratio'], pct=True))}
{kv("自己資本比率（期間最低）", fmt(sv['min_equity_ratio'], pct=True))}
{kv("ネット有利子負債", oku(sv['net_debt']))}
{kv("ネットD/E", fmt(sv['net_debt_to_equity'], digits=2))}
{kv("赤字時の持ちこたえ年数", fmt(sv['survive_years_if_loss']) if sv['survive_years_if_loss'] else "—（赤字年なし）")}
</div></div>

<h2>平常時の利益で見た株価の割安さ</h2>
<div class="card"><div class="grid">
{kv("平常時の売上（10年の中央値）", oku(v['normalized_sales']))}
{kv("平常時の利益率（10年の中央値）", fmt(v['normalized_margin'], pct=True))}
{kv("平常時の経常利益", oku(v['normalized_ordinary']))}
{kv("平常時の1株利益（税引後）", fmt(v['normalized_eps'], digits=2) + " 円")}
{kv("平常時の利益で見たPER", fmt(v['normalized_per']))}
{kv(f"理論株価（PER {v['midcycle_per']:.0f} 倍で評価）", fmt(v['fair_value']) + " 円")}
{kv("期待リターン（理論株価 ÷ 現在値）", fmt(v['expected_return_x'], x=True))}
{kv("PBR（株価 ÷ 1株純資産）", fmt(v['pbr'], digits=2))}
</div><p class="note">景気循環株は谷でPERが高く・山でPERが低く見える。だから今の利益ではなく、
山谷をならした「平常時の利益」で評価する。期待リターン2倍（+100%）未満は原則見送り。</p></div>

<h2>清算価値（下値のメド）</h2>
<div class="card"><div class="grid">
{kv("清算価値", oku(liq['value']))}
{kv("1株あたり清算価値", fmt(liq['per_share']) + " 円")}
{kv("清算価値までの下落余地", fmt(liq['downside_to_liquidation'], pct=True))}
</div><p class="note">換金率: 現金100% / 売掛80% / 在庫50% / 有形固定資産70% /
無形0% / 投資その他70%（asd.txt 準拠）。</p></div>

<h2>チェックリスト A / B / C（自動判定）</h2>
{mk("A_cycle_not_structural")}
{mk("B_survive_to_next_peak")}
{mk("C_operating_leverage_upside")}

<h2>フェーズ・カタリスト（手入力メモ）</h2>
<div class="card">
<p class="note">下のメモはこのブラウザにのみ保存されます（他の人には見えません）。</p>
<label>いま循環のどこか（在庫循環・稼働率・市況スプレッド・先物カーブ）
<textarea id="m_phase" placeholder="例: 鋼材スプレッドが損益分岐点割れ。稼働率は過去レンジ下限。在庫調整は最終盤。"></textarea></label>
<label style="display:block;margin-top:.6rem">上がる引き金（減産・統合 / 需要イベント / 自助努力 / 在庫調整完了 / 資本イベント）
<textarea id="m_cat"></textarea></label>
<label style="display:block;margin-top:.6rem">進捗を測る KPI
<textarea id="m_kpi"></textarea></label>
<label style="display:block;margin-top:.6rem">カタリスト強度（0〜3）
<input id="m_score" type="number" min="0" max="3" step="1" style="width:5rem"></label>
<p class="note" id="saved"></p>
</div>
<script>
const K="tachan1:{a['code']}";
const F=["m_phase","m_cat","m_kpi","m_score"];
try{{const d=JSON.parse(localStorage.getItem(K)||"{{}}");
 F.forEach(f=>{{if(d[f]!=null)document.getElementById(f).value=d[f]}});}}catch(e){{}}
function save(){{const d={{}};F.forEach(f=>d[f]=document.getElementById(f).value);
 try{{localStorage.setItem(K,JSON.stringify(d));
 document.getElementById("saved").textContent="保存しました "+new Date().toLocaleString();}}catch(e){{}}}}
F.forEach(f=>document.getElementById(f).addEventListener("input",save));
</script>
"""
    return page(f"{a['code']} {a['name']}", body, depth=1)


_CHECK_TITLE = {
    "A_cycle_not_structural": "A. 「谷」か「構造的な衰退」か",
    "B_survive_to_next_peak": "B. 次の山まで生き残れるか",
    "C_operating_leverage_upside": "C. 山でどれだけ跳ねるか",
}


def main() -> None:
    shortlist = json.loads((DATA / "shortlist.json").read_text("utf-8"))
    market = json.loads((DATA / "market" / "commodities.json").read_text("utf-8")) \
        if (DATA / "market" / "commodities.json").exists() else {}

    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "company").mkdir(parents=True)

    (DOCS / "index.html").write_text(build_index(shortlist), encoding="utf-8")

    n = 0
    for row in shortlist["rows"]:
        p = DATA / "analysis" / f"{row['code']}.json"
        if not p.exists():
            continue
        a = json.loads(p.read_text("utf-8"))
        (DOCS / "company" / f"{row['code']}.html").write_text(
            build_company(a, market), encoding="utf-8")
        n += 1

    (DOCS / "shortlist.json").write_text(
        json.dumps(shortlist, ensure_ascii=False), encoding="utf-8")
    print(f"docs/: index + {n} 銘柄ページ")


if __name__ == "__main__":
    main()
