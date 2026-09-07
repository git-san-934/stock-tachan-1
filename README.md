# シクリカルバリュー・スクリーナー

景気循環業界で「循環の谷」にいて、次の山まで生き残れて、山で大きく跳ねる可能性が
ある割安株を、東証33業種のシクリカル業種から機械的に絞り込む。

手法の考え方は [`シクリカルバリュー投資.md`](シクリカルバリュー投資.md)、
開発ルールは [`開発.md`](開発.md)、企業分析レポートの書式は [`asd.txt`](asd.txt)。

**LLM もサーバーも使わない。完全無料。** データは EDINET・Yahoo Finance・FRED から。

## 漏斗（段階0〜5）

| 段階 | 内容 | 主な条件 |
|---|---|---|
| 0 | ユニバース | 東証33業種のシクリカル業種（`config/sectors.json`） |
| ① 割安 | 外形的な割安性 | PBR<1.0 / 正常化PER<8 / 期待リターン≥2倍 のいずれか |
| ② 循環性 | そもそもシクリカルか | 利益弾性≥2 / 利益率のブレ大 / 過去に赤字 / DOL高 |
| ③ 谷 | いま循環の谷か | 経常利益率が過去下位40% / 赤字 / 市況が谷寄り |
| ④ 非衰退 | 構造的衰退でないか | 売上CAGR≥−2% かつ 直近ピーク≥過去ピーク×0.9 |
| ⑤ 生存力 | 次の山まで生き残れるか | 自己資本比率≥25% かつ ネットD/E≤1.0 |

全段階を通過した銘柄を「漏斗通過」として上位に並べ、自動スコア（割安40 / 谷25 /
生存35）で順位付けする。**カタリスト（引き金）は自動化せず、銘柄詳細ページの
手入力メモで管理する。**

## データの流れ

```
config/sectors.json ──┐
                      ▼
scripts/fetch_universe.py     J-Quants /listed/info（または JPX data_j を .xlsx 保存）
   │                          → data/universe.json（シクリカル業種の銘柄一覧）
   ▼
scripts/fetch_yuho_index.py   EDINET 書類一覧を6年さかのぼり有報を索引化
   │                          → cache/yuho_index.json
   ▼
scripts/fetch_financials.py   最新有報＋約5年前の有報の「主要な経営指標等の推移」を
   │                          マージ（1書類で5年ぶん）→ 最大10年の財務
   │                          BS明細・発行済株式数も最新有報から
   │                          → data/<code>/financials.json
   ▼
scripts/fetch_prices.py       Yahoo Finance chart API（月次10年）
   │                          → data/<code>/prices.json
   ▼
scripts/fetch_market.py       FRED（原油・鉄鉱石・石炭・銅ほか＋日本鉱工業生産）
   │                          → data/market/commodities.json
   ▼
scripts/analyze.py            循環性 / トラフ / 構造 / 生存力 / 正常化利益 /
   │                          バリュエーション / 清算価値 / チェックリストA・B・C / スコア
   │                          → data/analysis/<code>.json
   ▼
scripts/build_shortlist.py    漏斗を適用してランキング → data/shortlist.json
   ▼
site/build.py                 docs/ に静的サイト（ランキング＋銘柄詳細）
   ▼
GitHub Pages で公開 → ポータル https://git-san-934.github.io/portal/ に追加
```

`scripts/update_all.py` が 0〜⑤を通しで実行する。

## セットアップ

1. EDINET API キー（無料）: https://api.edinet-fsa.go.jp/
2. `.env`（`.env.example` をコピー）:
   ```
   EDINET_API_KEY=xxxxxxxx
   # ユニバースを J-Quants から作る場合のみ（無料アカウント）:
   # JQUANTS_REFRESH_TOKEN=...   または JQUANTS_MAIL= / JQUANTS_PASS=
   ```
   J-Quants を使わない場合は JPX「東証上場銘柄一覧」(data_j.xls) をブラウザで開いて
   `.xlsx` 形式で `cache/universe.xlsx` に保存し、`--universe-xlsx` を付ける。
3. `pip install -r requirements.txt`

## 使い方（ローカル）

```bash
# 1 銘柄だけ通して確認
python scripts/run_pipeline.py 5401

# ユニバースと有報索引を作る（初回。索引は6年ぶんで 6〜10 分）
python scripts/fetch_universe.py
python scripts/fetch_yuho_index.py --years 6

# 全体更新（財務は data/<code>/financials.json 単位でスキップ・再開可）
python scripts/update_all.py               # 初回は 1〜2 時間
python scripts/update_all.py --limit 50    # 動作確認（先頭50社）
python scripts/update_all.py --skip-index  # 索引の再収集を省く

# 株価だけまとめて取り直す（Yahoo。ローカルで実行してコミットする）
python scripts/fetch_prices.py --universe --max-age-days 20

# サイト生成・ローカル確認
python site/build.py
python -m http.server -d docs 8000
```

## GitHub Pages 公開（初回のみ）

1. リポジトリを作成して push（`stock-tachan-1`）
2. Settings → Secrets and variables → Actions に `EDINET_API_KEY` を登録
3. Settings → Pages → Source を **GitHub Actions**
4. Actions の `update` を手動実行（以降は毎月1日・15日）
5. 公開 URL をポータル（`../portal/index.html` の `<main class="apps">`）に追加

## ファイル構成

| パス | 役割 |
|---|---|
| `config/sectors.json` | シクリカル業種の定義と、業種→市況シリーズの対応 |
| `scripts/common.py` | パス・.env・HTTP・回帰(OLS)・統計ヘルパー |
| `scripts/edinet.py` | EDINET API v2（書類一覧キャッシュ・ダウンロード） |
| `scripts/xbrl_csv.py` | 有報 CSV(type=5) のパース |
| `scripts/jquants.py` | J-Quants（上場銘柄マスタのみ） |
| `scripts/fetch_universe.py` | ユニバース生成 → `data/universe.json`（コミット対象） |
| `scripts/fetch_yuho_index.py` | 有報索引 → `cache/yuho_index.json`（Git 管理外） |
| `scripts/fetch_financials.py` | 10年財務・BS明細 → `data/<code>/financials.json` |
| `scripts/fetch_prices.py` | 月次10年株価 → `data/<code>/prices.json` |
| `scripts/fetch_market.py` | 市況（FRED）→ `data/market/commodities.json` |
| `scripts/analyze.py` | 全指標・チェックリスト・スコア → `data/analysis/<code>.json` |
| `scripts/build_shortlist.py` | 漏斗適用・ランキング → `data/shortlist.json` |
| `scripts/update_all.py` | 0〜⑤の通し実行 |
| `site/build.py` | 静的サイト生成（`docs/` はコミットせず CI でビルド） |

## 限界・注意

- 財務値は XBRL からの自動抽出。IFRS・銀行・特殊決算で取りこぼしがある。
- 「主要な経営指標等の推移」は連結ベース。個別しか出さない会社は個別値。
- コスト分解は「総費用≒売上−経常利益」の回帰による近似。製造原価明細は未使用。
- 市況フェーズは商品市況の15年パーセンタイルによる粗い目安。BDI（海運）は手動。
- 株価は Yahoo の調整後終値、時価総額は 株価×発行済株式数（自己株控除前）。
- **これはスクリーニング（一次ふるい）であって推奨ではない。** 通過銘柄は
  有報を読み、循環フェーズとカタリストを人が確認したうえで判断する。
