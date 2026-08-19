# AI Radar

**AIアップデート**と**プロダクトアップデート（広告・検索体験）**の2軸で情報を集約し、
そのまま資料化に流せる形で書き出すブラウザアプリ。

公開URL: **https://logmin.github.io/ai-radar/**
ローカルでは `index.html` をダブルクリックしても動く（サーバー不要）。

## タブ構成

| タブ | 中身 |
|---|---|
| AIアップデート | モデル・機能リリース、研究、業界動向 |
| プロダクト | 広告プロダクト、検索体験、計測、アドテクの仕様変更 |
| 週刊AI | AGIラボ「週刊AI」だけを号数順に |
| 保存済み | ★を付けた記事 |

軸を切り替えるとアクセント色とトピック体系が入れ替わる（AI軸=青、プロダクト軸=緑）。

## 機能

- キーワードAND検索（`/` キーでフォーカス、`Esc` でクリア）
- ソース／トピック／期間（1週間・1か月・3か月・すべて）の絞り込み、「未読のみ」トグル
- 記事クリックで新しいタブで開き、既読になって薄く表示
- ★＝あとで読む。既読・保存は localStorage（キー `ai-radar-v1`）
- **サマリ出力** … 下記
- ライト／ダーク切替、スマホ幅対応

### サマリ出力（資料化用）

「サマリ出力」ボタンで、**今の絞り込み条件のまま** Markdown を書き出す。
軸 → トピック順にグループ化され、各記事はタイトル・ソース・日付・URL・要約が付く。

```
# AI Radar サマリ
対象期間: 2026-07-20 〜 2026-08-19
件数: 119件

## プロダクトアップデート

### 検索・SEO（9件）
- **Google's third spam update of 2026 hits every language and region**
  PPC Land / 2026-08-19 / https://ppc.land/...
  Rollout began at 09:27 Pacific on August 18 and may run for several days...
```

「期間=1か月」で出してコピーすれば、そのまま月次資料の素材になる。

## データ更新

```bash
python C:/Users/S19122/ai-radar/build.py
```

毎朝8:33に自動実行される（scheduled task `ai-radar-sync`）。
`build.py` がフィードを取得し、AI/プロダクトの2軸に振り分け、重複排除・トピック分類して
`data.js`（`window.AIRADAR_DATA`）を書き出す。アプリは `data.js` を読むだけなので、
ブラウザから直接スクレイピングする必要がなく CORS 制約を受けない。

### 累積マージ方式（重要）

`build.py` は**既存の `data.js` を読み込んで新着だけを足す**。まっさらに作り直さない。

これは Search Engine Roundtable のRSSが**最新15件（約1.5日分）しか保持していない**ため。
毎回作り直す方式だと、実行をスキップした日の記事が永久に失われる。累積方式なら
1日1回の実行で履歴が積み上がり、月次で振り返れる。

各フィードの保持期間の目安: SER 1.5日 / PPC Land 5日 / Google Ads Developer 2か月 /
blog.google 3か月。**SERが律速なので、自動更新を止めないこと。**

`data.js` に貯める期間は `KEEP_DAYS`（既定365日）、上限は `MAX_ITEMS`（4000件）。
フィードごとに `max_age` を書けば、そのソースだけ鮮度上限を変えられる（既定は `MAX_AGE_DAYS`=120日）。

貯めたデータには**毎回その時点のフィルタとトピック規則を再適用する**。
これがないと、フィルタを厳しくしても過去に取り込んだノイズが永久に残る。
ソースの `axis` を付け替えた場合も既存データが追従する。

### 収集元

**AIアップデート軸**

| 区分 | ソース |
|---|---|
| ★最重要 | AGIラボ（chatgpt-lab.com/rss）/ チャエン（note） |
| 国内 | ITmedia AI+ / ITmedia NEWS / 日経(Google News経由) / AINOW / Publickey / Zenn(AI) / ML_Bear(Zenn) / ML_Bear Times / ASCII.jp / PC Watch / 日経xTECH / GIGAZINE / MITTR Japan |
| 海外 | TechCrunch AI / Hugging Face / 9to5Google(新製品) |
| 公式 | OpenAI / Google AI / Google DeepMind |

**プロダクトアップデート軸**

| 区分 | ソース |
|---|---|
| ★最重要 | Search Engine Roundtable（`/index.rdf`） |
| 専門メディア | PPC Land / 9to5Google(検索カテゴリ) |
| 公式 | Google Ads Developer Blog / blog.google Ads & Commerce |

### Xアカウントの代替ソース

Xは無料APIが廃止されていて自動取得できないため、同じ人・同じ媒体が発信している
RSSを持つ場所に置き換えている。

| 追っていたX | 代替ソース | 備考 |
|---|---|---|
| @ctgptlb（AGIラボ） | `chatgpt-lab.com/rss` | `agi-labo.com/home` はnoteと同一コンテンツなので追加不要 |
| @masahirochaen（チャエン） | `note.com/chaen_channel/rss` | 週刊AIニュースもここに載る |
| @MLBear2 | `zenn.dev/ml_bear/feed` ＋ `ml-bear-times.com/feed` | Zennは数か月おきなので `max_age` を緩めている。ML_Bear Timesは朝夕2回の自動生成ダイジェスト（タイトルが日付なので中身は開いて読む） |
| @itmedia_news | `rss.itmedia.co.jp/rss/2.0/news_bursts.xml` | AI以外も流れるので `filter:"ai"` |
| @nikkei | `news.google.com/rss/search?q=AI+site:nikkei.com` | 日経は公式RSSを廃止済み。Google News RSS で代替。タイトル末尾の「 - nikkei.com」は自動で削る |

### 9to5Google の扱い（2フィードに分けている）

全体フィードはPixel/Android記事が大半で、広告・検索の記事は100件中1件程度しかない。
そのため用途を分けている。

- **検索カテゴリ** `guides/google-search/feed/` → プロダクト軸。検索プロダクトの話が中心
- **全体フィード** `feed/` → AI軸。`filter:"launch"` で「AI絡み or 新デバイス」×「発表・提供開始」
  だけを通す。日々のPixel小改良、セール、レビュー、噂、キーノート実況、色違いは落とす（100件→11件）

`filter:"launch"` の判定語は `LAUNCH_SUBJECT` / `LAUNCH_ANNOUNCE` / `LAUNCH_EXCLUDE`。
`first` `new` `officially` は弱すぎて機種の細かい話まで通すので意図的に入れていない。
キーワードによる推定なので、取りこぼしと軽いノイズは残る。

### 収集元の追加・変更

`build.py` の `FEEDS` に1行足すだけ。

```python
{"id": "webtan", "name": "Web担", "axis": "product", "kind": "media",
 "url": "https://webtan.impress.co.jp/rss/index.rdf", "filter": "product"},
```

- `axis` … `ai` / `product`
- `kind` … `main`(★最重要) / `official` / `media` / `jp` / `global`
- `filter` … `None`=全記事採用 / `"ai"` / `"product"`（キーワードで絞る）

トピック分類は `AI_TOPIC_RULES` / `PRODUCT_TOPIC_RULES` にある。
英数キーワードは単語境界でマッチさせているので、`ai` が `Fairphone` に当たることはない。
逆に `ad` や `advertis` のような誤爆しやすい語は意図的に除外している。

## ピックアップ（Claudeの横断検索ぶん）

RSSを持たないサイトや、検索で拾った記事は `extra.json` に書くと
`build.py` が「ピックアップ」として取り込む。

```json
[
  {
    "title": "記事タイトル",
    "url": "https://example.com/article",
    "sourceName": "媒体名",
    "axis": "product",
    "date": "2026-08-19",
    "summary": "一言メモ（省略可）",
    "topics": ["広告プロダクト"]
  }
]
```

`axis` の既定は `ai`。`date` / `summary` / `topics` は省略可。
Claudeに「AI Radarのピックアップを更新して」と頼めば、Web検索して書き換え、`build.py` まで回す。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | アプリ本体（バニラJS、単一ファイル） |
| `data.js` | 記事データ。`build.py` が自動生成するので手で編集しない |
| `build.py` | フィード収集スクリプト |
| `extra.json` | 手動・検索で足す記事（任意） |

## 制約

- 週刊AIの本文はAGIラボの会員記事のため、アプリではタイトルと冒頭のみ。全文は記事リンクから。
- X（旧Twitter）の自動収集は無料APIの廃止とログイン壁により不可。必要な投稿は `extra.json` に手で追加する。
- 検索API（Brave等）連携はキー管理のためのサーバーが必要なので未実装。Claude がWeb検索して `extra.json` に反映する形で代替している。
- リポジトリは Public。**社内限定の情報や自分の所見をこのリポジトリに置くと公開される**ので入れない。
