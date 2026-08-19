# AI Radar

AGIラボ「週刊AI」を軸に、国内外のAIニュースを1画面に集約するブラウザアプリ。

## 使い方

`index.html` をダブルクリックするだけ。サーバー不要・インストール不要。
Chrome / Edge のブックマークに入れておくと日常的に開けます。

- **週刊AI** タブ … AGIラボの週刊AI（#79 まで収録）だけを号数順に表示
- **すべて** タブ … 週刊AI＋国内外メディア＋開発元公式を時系列で横断表示
- **保存済み** タブ … ★を押した記事だけ表示
- 検索ボックス（`/` キーでフォーカス）… タイトル・本文・ソース・タグを横断。スペース区切りでAND検索
- ソース／トピック／期間 の絞り込み、「未読のみ」トグル
- 記事をクリックすると新しいタブで開き、既読になって薄く表示される
- ★＝あとで読む。既読・保存は localStorage（キー `ai-radar-v1`）に保存

## データ更新

```bash
python C:/Users/S19122/ai-radar/build.py
```

`build.py` が各フィードを取得し、AI関連記事だけを抽出・重複排除・トピック分類して
`data.js`（`window.AIRADAR_DATA`）を書き出します。アプリは `data.js` を読むだけなので、
ブラウザから直接スクレイピングする必要がなく CORS 制約を受けません
（log you の `schedule.js` と同じ方式）。

### 収集元

| 区分 | ソース |
|---|---|
| メイン | AGIラボ（chatgpt-lab.com/rss） |
| 国内 | ITmedia AI+ / AINOW / Publickey / Zenn(AI) / ASCII.jp / PC Watch / 日経xTECH / GIGAZINE / MITTR Japan |
| 海外 | TechCrunch AI / Hugging Face |
| 開発元公式 | OpenAI / Google AI / Google DeepMind |

汎用メディア（ASCII, PC Watch, GIGAZINE 等）は AI キーワードで絞り込んでから収録します。
1フィードあたり最新25件（メインは60件）、直近120日分が対象です。

### 収集元の追加・変更

`build.py` の `FEEDS` に1行足すだけです。

```python
{"id": "webtan", "name": "Web担", "kind": "jp",
 "url": "https://webtan.impress.co.jp/rss/index.rdf", "ai_only": False},
```

`kind` は `main` / `jp` / `global` / `official`、`ai_only` を `False` にすると
AIキーワードで絞り込みます。トピックタグの分類ルールは `TOPIC_RULES` にあります。

## ピックアップ（Claudeの横断検索ぶん）

RSSを持たないサイトや、検索で拾った記事は `extra.json` に書くと
`build.py` が「ピックアップ」として取り込みます。

```json
[
  {
    "title": "記事タイトル",
    "url": "https://example.com/article",
    "sourceName": "媒体名",
    "date": "2026-08-19",
    "summary": "一言メモ（省略可）",
    "topics": ["広告・マーケ"]
  }
]
```

`date` / `summary` / `topics` は省略可（`topics` は自動判定されます）。
Claudeに「AI Radarのピックアップを更新して」と頼めば、Web検索して `extra.json` を
書き換え、`build.py` を回すところまでやります。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | アプリ本体（バニラJS、単一ファイル） |
| `data.js` | 記事データ。`build.py` が自動生成するので手で編集しない |
| `build.py` | フィード収集スクリプト |
| `extra.json` | 手動・検索で足す記事（任意） |

## 制約

- 週刊AIの本文はAGIラボの会員記事のため、アプリではタイトルと冒頭のみ表示されます。全文は記事リンクから。
- X（旧Twitter）の自動収集は無料APIの廃止とログイン壁により不可。必要な投稿は `extra.json` に手で追加する運用になります。
- 検索API（Brave等）連携はキー管理のためのサーバーが必要なので未実装。現状は Claude がWeb検索して `extra.json` に反映する形で代替しています。
