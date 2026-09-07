"""レビュー用の1ファイル完結 HTML を作る（別端末からでも見られるよう Artifact 公開用）。

  python site/build_artifact.py   →  cache/review.html

data/shortlist.json ＋ data/analysis/*.json ＋ data/market/commodities.json を
すべて埋め込み、一覧・詳細をブラウザ内で描画する。GitHub Pages 版とは別物。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "cache" / "review.html"

FUNNEL_LABELS = ["⓪規模", "①割安", "②循環性", "③谷", "④非衰退", "⑤生存力", "⑥上値"]
FUNNEL_KEYS = ["s0_size", "s1_cheap", "s2_cyclical", "s3_trough",
               "s4_structural_ok", "s5_survivable", "s6_upside"]

CSS = """
:root{
  --bg:#f7f5f0; --panel:#fffdf9; --card:#ffffff; --text:#23201b; --sub:#6f675c;
  --line:#e6e1d6; --line-strong:#d8d1c2; --head:#efe9dc;
  --accent:#c8502d; --accent-soft:#f0d9cf;
  --ok:#2e7d5b; --warn:#b7791f; --ng:#b23b3b;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#1b1916; --panel:#232019; --card:#282420; --text:#f1ece3; --sub:#a89f90;
  --line:#3a3529; --line-strong:#4a4335; --head:#2d281f;
  --accent:#e2712f; --accent-soft:#3c2b1f;
  --ok:#4fae86; --warn:#d9a441; --ng:#e07a7a;
}}
:root[data-theme="dark"]{
  --bg:#1b1916; --panel:#232019; --card:#282420; --text:#f1ece3; --sub:#a89f90;
  --line:#3a3529; --line-strong:#4a4335; --head:#2d281f;
  --accent:#e2712f; --accent-soft:#3c2b1f;
  --ok:#4fae86; --warn:#d9a441; --ng:#e07a7a;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.6;
  font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
  font-variant-numeric:tabular-nums}
a{color:var(--accent)}
.wrap{max-width:1240px;margin:0 auto;padding:1.6rem 1rem 5rem}
h1{font-size:1.45rem;margin:.1rem 0;letter-spacing:.01em;text-wrap:balance}
h2{font-size:1rem;margin:1.7rem 0 .55rem;padding-left:.55rem;
  border-left:3px solid var(--accent)}
.lede{color:var(--sub);font-size:.9rem;max-width:64ch}
.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:.7rem;color:var(--sub)}
.badge{display:inline-block;background:var(--ok);color:#fff;border-radius:.3rem;
  padding:.05rem .45rem;font-size:.72rem;vertical-align:.1em}
.controls{display:flex;flex-wrap:wrap;gap:.55rem;align-items:center;margin:1.1rem 0 .6rem}
select,input,button{font:inherit;padding:.36rem .55rem;background:var(--card);
  color:var(--text);border:1px solid var(--line-strong);border-radius:.4rem}
button{cursor:pointer}
button:focus-visible,select:focus-visible,input:focus-visible,tr:focus-visible{
  outline:2px solid var(--accent);outline-offset:2px}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:.6rem;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:.84rem;min-width:940px}
th,td{padding:.44rem .55rem;text-align:right;white-space:nowrap;
  border-bottom:1px solid var(--line)}
tbody tr:last-child td{border-bottom:0}
th{background:var(--head);position:sticky;top:0;cursor:pointer;font-weight:600;z-index:1}
th .ar{color:var(--accent);font-size:.7em}
td.l,th.l{text-align:left}
tbody tr{cursor:pointer}
tbody tr:hover{background:var(--head)}
.pill{display:inline-block;min-width:1.25em;text-align:center;border-radius:.28rem;
  padding:0 .2rem;font-size:.75rem;line-height:1.5}
.f1{background:var(--ok);color:#fff}.f0{background:var(--line);color:var(--sub)}
.mk{font-weight:700;padding:0 .1em}
.mk.ok{color:var(--ok)}.mk.warn{color:var(--warn)}.mk.ng{color:var(--ng)}
.scorebar{display:inline-block;height:.5rem;border-radius:.25rem;background:var(--accent);
  vertical-align:.05em;min-width:2px}
.detail{position:fixed;inset:0;background:var(--bg);overflow-y:auto;z-index:10;
  animation:slide .18s ease}
@keyframes slide{from{transform:translateX(1.5rem);opacity:.4}to{transform:none;opacity:1}}
@media (prefers-reduced-motion:reduce){.detail{animation:none}}
.detail .wrap{padding-top:1rem}
.backbar{display:flex;gap:.8rem;align-items:center;position:sticky;top:0;
  background:var(--bg);padding:.5rem 0 .7rem;border-bottom:1px solid var(--line);z-index:2}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.55rem 1.4rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:.55rem;
  padding:.95rem 1.05rem;margin:.7rem 0}
.kv{font-size:.92rem}
.kv b{display:block;color:var(--sub);font-weight:400;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.04em;margin-bottom:.05rem}
.note{font-size:.84rem;color:var(--sub)}
.legend{font-size:.76rem;color:var(--sub);display:flex;gap:1rem;flex-wrap:wrap;margin-top:.4rem}
.checkrow{display:flex;gap:.6rem;align-items:baseline}
.checkrow .big{font-size:1.2rem}
svg{max-width:100%;height:auto;display:block}
table.mini{min-width:0;width:auto;font-size:.8rem;margin-top:.5rem}
table.mini td,table.mini th{border-bottom:1px solid var(--line);padding:.3rem .6rem}
footer{margin-top:3rem;color:var(--sub);font-size:.8rem;max-width:64ch}
textarea{width:100%;font:inherit;padding:.5rem;background:var(--panel);color:var(--text);
  border:1px solid var(--line-strong);border-radius:.4rem;min-height:3.4rem}
"""


def main() -> None:
    shortlist = json.loads((DATA / "shortlist.json").read_text("utf-8"))
    market = json.loads((DATA / "market" / "commodities.json").read_text("utf-8"))
    analyses = {}
    for r in shortlist["rows"]:
        p = DATA / "analysis" / f"{r['code']}.json"
        if p.exists():
            analyses[r["code"]] = json.loads(p.read_text("utf-8"))

    st = shortlist["stats"]
    payload = {
        "generated": shortlist["generated"],
        "stats": st,
        "rows": shortlist["rows"],
        "analyses": analyses,
        "funnelLabels": FUNNEL_LABELS,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) \
        .replace("<", "\\u003c").replace("\u2028", " ").replace("\u2029", " ")

    html = f"""<title>シクリカルバリュー・スクリーナー</title>
<style>{CSS}</style>

<div id="app" class="wrap">
  <p class="eyebrow">EDINET 有価証券報告書 ＋ Yahoo Finance ＋ FRED</p>
  <h1>シクリカルバリュー・スクリーナー <span class="badge">レビュー版</span></h1>
  <p class="lede">景気循環業界で「循環の谷」にいて、次の山まで生き残れて、山で大きく
  跳ねる可能性がある割安株を、東証33業種のシクリカル業種から機械的に絞り込む。
  行をタップすると銘柄の詳細（10年財務・コスト構造・チェックリストA/B/C）が開く。</p>
  <p class="note">生成 {st['analyzed']} 社分析 ／ 漏斗通過
  <b>{st['pass_all']}</b> 社 ／ {shortlist['generated']}。
  漏斗: {' '.join(FUNNEL_LABELS)}（③谷 = 利益率が過去下位40% or 赤字 or 市況が谷寄り）。</p>

  <div class="controls">
    <label><input type="checkbox" id="onlypass" checked> 漏斗通過のみ</label>
    <select id="sector"><option value="">業種すべて</option></select>
    <input id="q" placeholder="コード / 銘柄名" size="16">
    <span class="note" id="count"></span>
  </div>

  <div class="tablewrap"><table id="t"><thead><tr>
    <th class="l" data-k="code">コード</th>
    <th class="l" data-k="name">銘柄</th>
    <th class="l" data-k="sector33">業種</th>
    <th data-k="market_cap_oku">時価総額<br>(億円)</th>
    <th data-k="auto_score">自動<br>スコア</th>
    <th data-k="_funnel">漏斗</th>
    <th data-k="expected_return_x">期待<br>リターン</th>
    <th data-k="normalized_per">正常化<br>PER</th>
    <th data-k="pbr">PBR</th>
    <th data-k="cyclicality">循環性</th>
    <th data-k="trough_score">トラフ度</th>
    <th data-k="market_phase_score">市況<br>フェーズ</th>
    <th data-k="equity_ratio">自己資本<br>比率</th>
    <th data-k="net_debt_to_equity">ネット<br>D/E</th>
    <th data-k="_abc">A/B/C</th>
  </tr></thead><tbody></tbody></table></div>

  <footer>
  出典: EDINET 有価証券報告書（主要な経営指標等の推移）・Yahoo Finance 調整後終値・
  FRED（IMF 商品市況）。財務値は XBRL からの自動抽出のため誤りを含む。
  これはスクリーニング（一次ふるい）であって推奨ではない。通過銘柄は有報を読み、
  循環フェーズとカタリストを人が確認したうえで判断すること。投資は自己責任で。
  </footer>
</div>

<div id="detail" hidden></div>

<script id="data" type="application/json">{blob}</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const FL=D.funnelLabels;
const ABC=["A_cycle_not_structural","B_survive_to_next_peak","C_operating_leverage_upside"];
const ABC_T={{A_cycle_not_structural:"A. 循環の谷か、構造的衰退か",
  B_survive_to_next_peak:"B. 次の山まで生き残れるか",
  C_operating_leverage_upside:"C. 山でどれだけ跳ねるか"}};
let sortK="auto_score",sortDir=-1;

const num=(v,d=1)=>v==null?"—":Number(v).toLocaleString(undefined,{{maximumFractionDigits:d}});
const pct=(v,d=0)=>v==null?"—":(v*100).toFixed(d)+"%";
const xR=v=>v==null?"—":v.toFixed(2)+"×";
const oku=v=>v==null?"—":Math.round(v/1e8).toLocaleString()+" 億円";
const mkClass=m=>m==="○"?"ok":m==="△"?"warn":"ng";
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));

// ---------- 一覧 ----------
const tb=document.querySelector("#t tbody");
const secSel=document.querySelector("#sector");
[...new Set(D.rows.map(r=>r.sector33))].sort().forEach(s=>{{
  const o=document.createElement("option");o.textContent=s;secSel.appendChild(o);}});

function phaseTxt(v){{if(v==null)return"—";
  if(v>=0.7)return"谷寄り "+pct(v);if(v<=0.4)return"山寄り "+pct(v);return"中立 "+pct(v);}}
function funnelCells(f){{return f.map((b,i)=>
  `<span class="pill ${{b?'f1':'f0'}}" title="${{FL[i]}}">${{b?'✓':'·'}}</span>`).join("");}}

function render(){{
  const onlyp=document.querySelector("#onlypass").checked;
  const sec=secSel.value;
  const q=document.querySelector("#q").value.trim().toLowerCase();
  let rows=D.rows.filter(r=>(!onlyp||r.pass_all)&&(!sec||r.sector33===sec)&&
    (!q||r.code.toLowerCase().includes(q)||(r.name||"").toLowerCase().includes(q)));
  rows.sort((a,b)=>{{
    let x=a[sortK],y=b[sortK];
    if(sortK==="_funnel"){{x=a.funnel.filter(Boolean).length;y=b.funnel.filter(Boolean).length;}}
    if(sortK==="_abc"){{const g=r=>ABC.reduce((n,k)=>n+(r.checklist[k]==="○"?1:r.checklist[k]==="△"?.5:0),0);
      x=g(a);y=g(b);}}
    x=x==null?-1e9:x;y=y==null?-1e9:y;
    return (x<y?-1:x>y?1:0)*sortDir;}});
  document.querySelector("#count").textContent=rows.length+" 社";
  const smax=Math.max(...rows.map(r=>r.auto_score||0),1);
  tb.innerHTML=rows.map(r=>`<tr tabindex="0" data-code="${{r.code}}">
    <td class="l">${{r.code}}</td>
    <td class="l">${{esc(r.name)}}</td>
    <td class="l">${{esc(r.sector33)}}</td>
    <td>${{num(r.market_cap_oku)}}</td>
    <td><b>${{num(r.auto_score)}}</b>
      <span class="scorebar" style="width:${{(r.auto_score||0)/smax*46}}px"></span></td>
    <td>${{funnelCells(r.funnel)}}</td>
    <td>${{xR(r.expected_return_x)}}</td>
    <td>${{num(r.normalized_per)}}</td>
    <td>${{num(r.pbr,2)}}</td>
    <td>${{pct(r.cyclicality)}}</td>
    <td>${{pct(r.trough_score)}}</td>
    <td>${{phaseTxt(r.market_phase_score)}}</td>
    <td>${{pct(r.equity_ratio)}}</td>
    <td>${{num(r.net_debt_to_equity,2)}}</td>
    <td>${{ABC.map(k=>`<span class="mk ${{mkClass(r.checklist[k])}}">${{r.checklist[k]}}</span>`).join("")}}</td>
  </tr>`).join("");
}}
document.querySelectorAll("#t th").forEach(th=>th.addEventListener("click",()=>{{
  const k=th.dataset.k;if(!k)return;
  if(k===sortK)sortDir*=-1;
  else{{sortK=k;sortDir=(k==="code"||k==="name"||k==="sector33")?1:-1;}}
  document.querySelectorAll("#t th .ar").forEach(a=>a.remove());
  const ar=document.createElement("span");ar.className="ar";
  ar.textContent=sortDir<0?" ▾":" ▴";th.appendChild(ar);
  render();}}));
["onlypass","sector","q"].forEach(id=>
  document.getElementById(id).addEventListener("input",render));
tb.addEventListener("click",e=>{{const tr=e.target.closest("tr");if(tr)openDetail(tr.dataset.code);}});
tb.addEventListener("keydown",e=>{{
  if(e.key==="Enter"){{const tr=e.target.closest("tr");if(tr)openDetail(tr.dataset.code);}}}});

// ---------- チャート ----------
function chart(fy,sales,ord,margin){{
  const P=[];for(let i=0;i<fy.length;i++)
    if(sales[i]!=null)P.push([fy[i],sales[i],ord[i],margin[i]]);
  if(P.length<2)return"<p class='note'>チャート用データ不足。</p>";
  const W=760,H=250,pad=34,n=P.length,bw=(W-2*pad)/n;
  const smax=Math.max(...P.map(p=>p[1]))||1;
  const os=P.map(p=>p[2]).filter(v=>v!=null);
  let omin=Math.min(0,...os),omax=Math.max(0.01,...os);
  const x=i=>pad+bw*(i+0.5);
  const yo=v=>H-pad-((v-omin)/((omax-omin)||1))*(H-2*pad);
  let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="売上と利益の10年推移">`;
  s+=`<line x1="${{pad}}" y1="${{H-pad}}" x2="${{W-pad}}" y2="${{H-pad}}" stroke="var(--line-strong)"/>`;
  if(omin<0)s+=`<line x1="${{pad}}" y1="${{yo(0).toFixed(1)}}" x2="${{W-pad}}" y2="${{yo(0).toFixed(1)}}" stroke="var(--line-strong)" stroke-dasharray="3 3"/>`;
  P.forEach((p,i)=>{{
    const sh=(p[1]/smax)*(H-2*pad)*0.6;
    s+=`<rect x="${{(x(i)-bw*0.32).toFixed(1)}}" y="${{(H-pad-sh).toFixed(1)}}" width="${{(bw*0.64).toFixed(1)}}" height="${{sh.toFixed(1)}}" fill="var(--line-strong)"/>`;
    if(p[2]!=null){{const a=yo(p[2]),b=yo(0);
      s+=`<rect x="${{(x(i)-bw*0.16).toFixed(1)}}" y="${{Math.min(a,b).toFixed(1)}}" width="${{(bw*0.32).toFixed(1)}}" height="${{Math.abs(a-b).toFixed(1)}}" fill="${{p[2]>=0?'var(--ok)':'var(--ng)'}}"/>`;}}
    s+=`<text x="${{x(i).toFixed(1)}}" y="${{H-pad+14}}" font-size="10" fill="var(--sub)" text-anchor="middle">${{p[0]}}</text>`;
  }});
  const ms=P.map(p=>p[3]).filter(v=>v!=null);
  if(ms.length>=2){{
    const mlo=Math.min(0,...ms),mhi=Math.max(0.01,...ms),rng=(mhi-mlo)||1;
    const ym=v=>pad+(1-(v-mlo)/rng)*(H-2*pad)*0.42;
    let d="M";P.forEach((p,i)=>{{if(p[3]!=null)d+=`${{d.length>1?" L":""}}${{x(i).toFixed(1)}},${{ym(p[3]).toFixed(1)}}`;}});
    s+=`<path d="${{d}}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
    P.forEach((p,i)=>{{if(p[3]!=null)s+=`<text x="${{x(i).toFixed(1)}}" y="${{(ym(p[3])-5).toFixed(1)}}" font-size="9" fill="var(--accent)" text-anchor="middle">${{(p[3]*100).toFixed(0)}}%</text>`;}});
  }}
  return s+"</svg>";
}}

// ---------- 詳細 ----------
const kv=(l,v)=>`<div class="kv"><b>${{esc(l)}}</b>${{v}}</div>`;
function openDetail(code){{
  const a=D.analyses[code];const box=document.getElementById("detail");
  if(!a){{return;}}
  const s=a.series,v=a.valuation,t=a.trough,sv=a.survival,stc=a.structural,
    liq=a.liquidation,cs=a.cost_structure;
  const pn=a.profit_basis||"経常利益";
  const ph=(t.market_phase_detail||[]).map(d=>
    `<tr><td class="l">${{esc(d.label)}}</td><td>${{esc(d.hint)}}</td>
     <td>${{pct(d.pctile)}}</td><td>${{d.yoy==null?"—":(d.yoy*100).toFixed(0)+"%"}}</td>
     <td>${{d.stale?"（古い）":""}}</td></tr>`).join("");
  const check=k=>{{const c=a.checklist[k];return `<div class="card checkrow">
    <span class="mk ${{mkClass(c.mark)}} big">${{c.mark}}</span>
    <div><b>${{esc(ABC_T[k])}}</b><div class="note">${{esc(c.note)}}</div></div></div>`;}};
  box.innerHTML=`<div class="wrap">
    <div class="backbar"><button id="back">← 一覧へ戻る</button>
      <span class="note">${{esc(a.code)}} ${{esc(a.name)}}</span></div>
    <h1>${{esc(a.code)}} ${{esc(a.name)}}
      ${{a.passes.pass_all?'<span class="badge">漏斗通過</span>':''}}</h1>
    <p class="note">${{esc(a.sector33)}}${{a.market?" · "+esc(a.market):""}} ·
      株価 ${{num(a.price)}} 円（${{esc(a.as_of_price)}}） ·
      時価総額 ${{num(a.market_cap_oku)}} 億円 ·
      決算 ${{a.fy_range?a.fy_range[0]+"–"+a.fy_range[1]:"?"}}（${{a.n_years}}年） ·
      自動スコア <b>${{num(a.auto_score)}}</b></p>

    <h2>売上高・${{esc(pn)}}・利益率（${{a.n_years}}年）</h2>
    <div class="card">${{chart(s.fy,s.sales,s.ordinary,s.ordinary_margin)}}
      <div class="legend"><span>■ 売上高（灰）</span>
      <span>■ ${{esc(pn)}}（緑=黒字 / 赤=赤字）</span>
      <span>— 利益率（橙・上部）</span></div></div>

    <h2>コスト構造（総費用≒売上−${{esc(pn)}} を売上に回帰）</h2>
    <div class="card"><div class="grid">
      ${{kv("変動費率",pct(cs.variable_cost_ratio,1))}}
      ${{kv("固定費（推定）",oku(cs.fixed_cost))}}
      ${{kv("限界利益率",pct(cs.contribution_margin,1))}}
      ${{kv("損益分岐点売上",oku(cs.breakeven_sales))}}
      ${{kv("営業レバレッジ DOL",num(cs.dol,2))}}
      ${{kv("回帰の当てはまり R²",num(cs.r2,2))}}
    </div><p class="note">DOL が高いほど、売上の変化で利益が大きく振れる（谷で赤字・山で急拡大）。</p></div>

    <h2>循環性</h2>
    <div class="card"><div class="grid">
      ${{kv("循環性スコア",pct(a.cyclicality.score))}}
      ${{kv("利益弾性（σ利益yoy / σ売上yoy）",num(a.cyclicality.elasticity,1))}}
      ${{kv("利益率のブレ（標準偏差）",pct(a.cyclicality.margin_stdev,1))}}
      ${{kv("過去に赤字の年",a.cyclicality.has_loss_year?"あり":"なし")}}
      ${{kv("ミッドサイクル利益率（中央値）",pct(a.cyclicality.median_margin,1))}}
    </div></div>

    <h2>いま循環の谷か</h2>
    <div class="card"><div class="grid">
      ${{kv("トラフ度（総合）",pct(t.score))}}
      ${{kv("直近の利益率",pct(t.latest_margin,1))}}
      ${{kv("利益率の過去パーセンタイル",pct(t.margin_pctile))}}
      ${{kv("市況フェーズ（1=谷 0=山）",num(t.market_phase_score,2))}}
      ${{kv("株価 10年パーセンタイル",pct(t.price_pctile_10y))}}
      ${{kv("10年高値からの下落率",pct(t.price_drawdown_10y))}}
    </div>${{ph?`<table class="mini"><thead><tr><th class="l">市況</th><th>フェーズ</th>
      <th>15年%タイル</th><th>前年比</th><th></th></tr></thead><tbody>${{ph}}</tbody></table>`
      :`<p class="note">この業種に紐づく自動取得の市況シリーズはありません。</p>`}}</div>

    <h2>構造縮小でないか（バリュートラップ判定）</h2>
    <div class="card"><div class="grid">
      ${{kv("売上 期間CAGR",pct(stc.sales_cagr,1))}}
      ${{kv("判定",stc.ok?"循環の範囲内":"要注意")}}
      ${{kv("構造縮小フラグ",stc.shrink_flag?"⚠ 立っている":"なし")}}
    </div><p class="note">EV化・脱炭素・デジタル代替・中国の恒常的過剰供給などで
    市場そのものが縮小していないか、定性的にも必ず確認する。</p></div>

    <h2>次の山まで生き残れるか</h2>
    <div class="card"><div class="grid">
      ${{kv("自己資本比率（直近）",pct(sv.equity_ratio))}}
      ${{kv("自己資本比率（期間最低）",pct(sv.min_equity_ratio))}}
      ${{kv("ネット有利子負債",oku(sv.net_debt))}}
      ${{kv("ネットD/E",num(sv.net_debt_to_equity,2))}}
      ${{kv("赤字時の持ちこたえ年数",sv.survive_years_if_loss?num(sv.survive_years_if_loss,1)+" 年":"—（赤字年なし）")}}
    </div></div>

    <h2>正常化利益とバリュエーション</h2>
    <div class="card"><div class="grid">
      ${{kv("正常化売上（全期間中央値）",oku(v.normalized_sales))}}
      ${{kv("正常化利益率（中央値）",pct(v.normalized_margin,1))}}
      ${{kv("正常化"+pn,oku(v.normalized_ordinary))}}
      ${{kv("正常化EPS（税率30%後）",num(v.normalized_eps,2)+" 円")}}
      ${{kv("正常化PER",num(v.normalized_per,1))}}
      ${{kv("理論株価（PER "+num(v.midcycle_per,0)+"）",num(v.fair_value,0)+" 円")}}
      ${{kv("期待リターン倍率",xR(v.expected_return_x))}}
      ${{kv("PBR（実績BPS）",num(v.pbr,2))}}
    </div><p class="note">シクリカルは谷で高PER・山で低PERになる。谷のPERではなく
    ミッドサイクル利益で評価する。期待リターン2倍未満は原則見送り。</p></div>

    <h2>清算価値（下値のメド）</h2>
    <div class="card"><div class="grid">
      ${{kv("清算価値",oku(liq.value))}}
      ${{kv("1株あたり清算価値",num(liq.per_share,0)+" 円")}}
      ${{kv("清算価値までの下落余地",pct(liq.downside_to_liquidation))}}
    </div><p class="note">換金率: 現金100% / 売掛80% / 在庫50% / 有形固定70% /
    無形0% / 投資その他70%（asd.txt 準拠）。</p></div>

    <h2>チェックリスト A / B / C（自動判定）</h2>
    ${{check("A_cycle_not_structural")}}
    ${{check("B_survive_to_next_peak")}}
    ${{check("C_operating_leverage_upside")}}

    <h2>フェーズ・カタリスト（手入力メモ）</h2>
    <div class="card"><p class="note">このブラウザにのみ保存されます。</p>
      <label>いま循環のどこか（在庫循環・稼働率・市況スプレッド・先物カーブ）
      <textarea id="m_phase"></textarea></label>
      <label style="display:block;margin-top:.5rem">上がる引き金
      <textarea id="m_cat"></textarea></label>
      <label style="display:block;margin-top:.5rem">進捗を測る KPI
      <textarea id="m_kpi"></textarea></label>
      <p class="note" id="saved"></p></div>
    <footer>スクリーニングであって推奨ではない。有報とカタリストを人が確認すること。</footer>
  </div>`;
  box.hidden=false;document.getElementById("app").hidden=true;
  window.scrollTo(0,0);
  document.getElementById("back").addEventListener("click",closeDetail);
  const K="tachan1:"+code,F=["m_phase","m_cat","m_kpi"];
  try{{const d=JSON.parse(localStorage.getItem(K)||"{{}}");
    F.forEach(f=>{{if(d[f])document.getElementById(f).value=d[f];}});}}catch(e){{}}
  const save=()=>{{const d={{}};F.forEach(f=>d[f]=document.getElementById(f).value);
    try{{localStorage.setItem(K,JSON.stringify(d));
      document.getElementById("saved").textContent="保存しました "+new Date().toLocaleString();}}catch(e){{}}}};
  F.forEach(f=>document.getElementById(f).addEventListener("input",save));
  history.pushState({{code}},"","#"+code);
}}
function closeDetail(){{
  document.getElementById("detail").hidden=true;
  document.getElementById("app").hidden=false;
  if(location.hash)history.pushState("","",location.pathname);
}}
window.addEventListener("popstate",e=>{{
  if(e.state&&e.state.code)openDetail(e.state.code);else closeDetail();}});

render();
if(location.hash.length>1&&D.analyses[location.hash.slice(1)])openDetail(location.hash.slice(1));
</script>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    kb = OUT.stat().st_size // 1024
    print(f"{OUT}  ({kb:,} KB, 銘柄 {len(analyses)})")


if __name__ == "__main__":
    main()
