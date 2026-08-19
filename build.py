# -*- coding: utf-8 -*-
"""
AI Radar - データ収集スクリプト

2軸で情報を集める:
  ai      … AIそのもののアップデート（モデル・機能・研究・業界動向）
  product … プロダクトのアップデート（広告・検索体験・計測などの仕様変更）

使い方:
    python C:/Users/S19122/ai-radar/build.py

既存の data.js を読み込んで新着だけを足す「累積マージ」方式。
RSSの保持期間が短いソース（SERは約1.5日分しか持たない）でも、
毎日回していれば履歴が積み上がる。

補完データ（Claudeがweb検索で拾った記事）は extra.json に置くと自動でマージされる。
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE_DIR, "data.js")
EXTRA_PATH = os.path.join(BASE_DIR, "extra.json")

JST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------- 収集元定義
# axis   : ai / product … アプリのメインタブ
# kind   : 表示上のグループ。main を付けたものは最重要ソース
# filter : None=全記事採用 / "ai"=AIキーワードで絞る / "product"=広告・検索キーワードで絞る
FEEDS = [
    # ===== AIアップデート軸 =====
    {"id": "agilabo",   "name": "AGIラボ",            "axis": "ai", "kind": "main",
     "url": "https://chatgpt-lab.com/rss", "filter": None},

    # ユーザーがXで追っているアカウントの代替ソース（Xは無料APIが無く自動取得できない）
    # @masahirochaen（チャエン）→ note
    {"id": "chaen",     "name": "チャエン",            "axis": "ai", "kind": "main",
     "url": "https://note.com/chaen_channel/rss", "filter": None},
    # @MLBear2 → Zenn記事 と 自動生成ニュースレター（朝夕2回）
    # Zennの投稿は数か月おきなので鮮度上限を緩める（既定120日だと0件になる）
    {"id": "mlbear",    "name": "ML_Bear (Zenn)",     "axis": "ai", "kind": "jp",
     # KEEP_DAYS(365)より大きくしても最後の間引きで落ちるので、それに合わせる
     "url": "https://zenn.dev/ml_bear/feed", "filter": None, "max_age": 360},
    {"id": "mlbeartimes", "name": "ML_Bear Times",    "axis": "ai", "kind": "jp",
     "url": "https://www.ml-bear-times.com/feed", "filter": None},
    # @itmedia_news → ITmedia NEWS 全体（AI以外も流れるのでキーワードで絞る）
    {"id": "itmnews",   "name": "ITmedia NEWS",       "axis": "ai", "kind": "jp",
     "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "filter": "ai"},
    # @nikkei → 日経は公式RSSを廃止しているので Google News 経由で拾う
    {"id": "nikkei",    "name": "日経（Google News経由）", "axis": "ai", "kind": "jp",
     "url": "https://news.google.com/rss/search?q=AI+site:nikkei.com&hl=ja&gl=JP&ceid=JP:ja",
     "filter": None, "clean_title": "gnews"},

    {"id": "itmedia",   "name": "ITmedia AI+",        "axis": "ai", "kind": "jp",
     "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "filter": None},
    {"id": "ainow",     "name": "AINOW",              "axis": "ai", "kind": "jp",
     "url": "https://ainow.ai/feed/", "filter": None},
    {"id": "publickey", "name": "Publickey",          "axis": "ai", "kind": "jp",
     "url": "https://www.publickey1.jp/atom.xml", "filter": "ai"},
    {"id": "zenn",      "name": "Zenn (AI)",          "axis": "ai", "kind": "jp",
     "url": "https://zenn.dev/topics/ai/feed", "filter": None},
    {"id": "ascii",     "name": "ASCII.jp",           "axis": "ai", "kind": "jp",
     "url": "https://ascii.jp/rss.xml", "filter": "ai"},
    {"id": "impress",   "name": "PC Watch",           "axis": "ai", "kind": "jp",
     "url": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf", "filter": "ai"},
    {"id": "xtech",     "name": "日経xTECH",           "axis": "ai", "kind": "jp",
     "url": "https://xtech.nikkei.com/rss/xtech-it.rdf", "filter": "ai"},
    {"id": "gigazine",  "name": "GIGAZINE",           "axis": "ai", "kind": "jp",
     "url": "https://gigazine.net/news/rss_2.0/", "filter": "ai"},
    {"id": "mittr",     "name": "MITTR Japan",        "axis": "ai", "kind": "jp",
     "url": "https://www.technologyreview.jp/feed/", "filter": "ai"},

    {"id": "techcrunch", "name": "TechCrunch AI",     "axis": "ai", "kind": "global",
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "filter": None},
    {"id": "hf",        "name": "Hugging Face",       "axis": "ai", "kind": "global",
     "url": "https://huggingface.co/blog/feed.xml", "filter": None},

    # 9to5Googleの全体フィードは、GoogleのAI新製品や他社の新デバイス発表だけを拾う。
    # 日々のPixel小改良・セール・レビュー・噂は filter="launch" で落とす。
    {"id": "9to5g",     "name": "9to5Google (新製品)", "axis": "ai", "kind": "global",
     "url": "https://9to5google.com/feed/", "filter": "launch"},

    {"id": "openai",    "name": "OpenAI",             "axis": "ai", "kind": "official",
     "url": "https://openai.com/news/rss.xml", "filter": None},
    {"id": "googleai",  "name": "Google AI",          "axis": "ai", "kind": "official",
     "url": "https://blog.google/technology/ai/rss/", "filter": None},
    {"id": "deepmind",  "name": "Google DeepMind",    "axis": "ai", "kind": "official",
     "url": "https://deepmind.google/blog/rss.xml", "filter": None},

    # ===== プロダクトアップデート軸 =====
    # SERのRSSは最新15件（約1.5日分）しか持たない。累積マージ前提で毎日回すこと。
    {"id": "ser",       "name": "Search Engine Roundtable", "axis": "product", "kind": "main",
     "url": "https://www.seroundtable.com/index.rdf", "filter": None},

    {"id": "ppcland",   "name": "PPC Land",           "axis": "product", "kind": "media",
     "url": "https://ppc.land/rss/", "filter": None},
    {"id": "adsdev",    "name": "Google Ads Developer", "axis": "product", "kind": "official",
     "url": "https://ads-developers.googleblog.com/feeds/posts/default?alt=rss", "filter": None},
    {"id": "blogads",   "name": "Google Ads & Commerce", "axis": "product", "kind": "official",
     "url": "https://blog.google/products/ads-commerce/rss/", "filter": None},
    # 9to5Googleの検索カテゴリは検索プロダクトの話なのでプロダクト軸に置く
    {"id": "9to5gs",    "name": "9to5Google (検索)",   "axis": "product", "kind": "media",
     "url": "https://9to5google.com/guides/google-search/feed/", "filter": None},
]

# filter="ai" のフィードを絞り込むキーワード
AI_KEYWORDS = [
    "ai", "生成ai", "人工知能", "llm", "chatgpt", "gpt", "claude", "gemini",
    "copilot", "openai", "anthropic", "nvidia", "機械学習", "ディープラーニング",
    "エージェント", "agent", "grok", "llama", "深層学習", "推論モデル",
]

# filter="product" のフィードを絞り込むキーワード（広告・検索プロダクト寄り）
# 単独の "ad" と "advertis" は入れない。前者は誤爆が多く、後者は
# "Samsung advertises it with…" のような広告プロダクト無関係の記事を拾ってしまう。
PRODUCT_KEYWORDS = [
    "ads", "広告", "search", "検索", "seo", "serp", "shopping", "merchant",
    "analytics", "ga4", "adsense", "campaign", "ai overviews", "ai mode",
    "search console", "bidding", "keyword", "discover", "sge",
]

# filter="launch" 用。「AI絡み or 新デバイス」×「発表・提供開始」で、0→1の発表だけを狙う。
# 末尾 * は語幹一致（announc* → announce / announced / announcement）。
LAUNCH_SUBJECT = AI_KEYWORDS + [
    "device", "hardware", "smart glasses", "glasses", "headset", "robot*",
    "wearable", "chip", "tablet", "laptop", "デバイス", "端末", "新製品",
    "tv", "watch", "earbuds", "speaker", "car", "xr", "vr", "ar",
]
LAUNCH_ANNOUNCE = [
    "announc*", "unveil*", "launch*", "introduc*", "debut*", "reveal*",
    "now available", "goes official", "rolling out", "rolls out", "roll out",
    "can now", "now lets", "now supports", "gains",
    "発表", "登場", "提供開始", "リリース", "公開", "刷新",
]
# セール・小ネタ・レビュー・噂・キーノート実況・色違いは 0→1 ではないので落とす。
# "first" / "new" / "officially" は弱すぎて機種の細かい話まで通してしまうので入れない。
LAUNCH_EXCLUDE = [
    "deal", "deals", "freebies", "sale", "discount", "coupon", "off",
    "how to", "tips", "review*", "hands-on", "hands on", "wallpaper*", "apk",
    "teardown", "rumor*", "leak*", "giveaway", "best", "vs", "comparison",
    "roundup", "live blog", "keynote", "colorway", "band", "edition",
    "what to expect", "everything you need",
    "値下げ", "セール", "レビュー", "噂", "リーク", "使い方",
]

# トピックタグ（軸ごとに別体系。表示順 = 優先度）
AI_TOPIC_RULES = [
    ("モデル",     ["gpt", "claude", "gemini", "llama", "grok", "opus", "sonnet", "haiku",
                    "モデル", "llm", "推論", "o3", "o4", "mistral", "qwen", "deepseek",
                    "ベンチマーク", "benchmark", "model"]),
    ("エージェント", ["エージェント", "agent", "codex", "claude code", "devin", "mcp",
                    "自律", "ワークフロー自動", "cursor", "copilot"]),
    # 動詞（発表/launch等）を入れると要約文に当たって過剰に付くので、名詞だけで判定する
    ("新製品・デバイス", ["新製品", "新型", "smart glasses", "headset", "wearable",
                    "hardware", "robot*", "earbuds", "tablet", "smartphone",
                    "端末", "デバイス", "スマホ", "ウェアラブル", "ロボット", "eyewear"]),
    ("画像・音声・動画", ["画像生成", "動画生成", "音声", "sora", "midjourney", "veo",
                    "stable diffusion", "音楽", "image", "video", "voice", "tts"]),
    ("ビジネス・資金", ["資金調達", "買収", "提携", "決算", "ipo", "投資", "billion",
                    "評価額", "funding", "acquire", "パートナーシップ", "億ドル", "兆円"]),
    ("規制・リスク", ["規制", "法案", "ガイドライン", "著作権", "プライバシー", "訴訟",
                    "セキュリティ", "リスク", "regulation", "lawsuit", "安全性", "safety"]),
    ("開発・技術",  ["api", "オープンソース", "oss", "sdk", "実装", "開発者",
                    "open source", "developer", "github", "コード"]),
    ("インフラ・半導体", ["gpu", "半導体", "データセンター", "nvidia", "tpu", "チップ",
                    "電力", "chip", "cloud", "クラウド基盤"]),
]

PRODUCT_TOPIC_RULES = [
    ("検索・SEO",   ["seo", "serp", "検索結果", "ranking", "core update", "spam update",
                    "index", "indexing", "search console", "sitemap", "クロール",
                    "structured data", "schema", "リッチリザルト"]),
    ("AI検索体験",  ["ai overviews", "ai mode", "chatgpt search", "perplexity", "aeo",
                    "generative search", "sge", "ai search", "llm", "chatgpt"]),
    ("広告プロダクト", ["ads", "advertis", "広告", "campaign", "pmax", "performance max",
                    "demand gen", "bidding", "入札", "shopping", "merchant", "adsense",
                    "keyword", "match type", "asset", "creative"]),
    ("計測・データ", ["analytics", "ga4", "conversion", "計測", "tracking", "tag",
                    "consent", "measurement", "attribution", "audience", "first-party"]),
    ("アドテク・媒体", ["ctv", "dooh", "ssp", "dsp", "programmatic", "inventory",
                    "publisher", "retail media", "supply path", "adtech", "in-app",
                    "takeover", "impression", "yield", "curation"]),
    ("API・開発",   ["api", "script", "sdk", "developer", "sandbox", "migration",
                    "deprecat", "version", "endpoint"]),
    ("ポリシー・規制", ["policy", "ポリシー", "規制", "antitrust", "lawsuit", "privacy",
                    "gdpr", "dma", "compliance", "ban", "違反"]),
]

TOPIC_RULES_BY_AXIS = {"ai": AI_TOPIC_RULES, "product": PRODUCT_TOPIC_RULES}
AXIS_LABEL = {"ai": "AIアップデート", "product": "プロダクトアップデート"}

# 1フィードあたりの採用上限、記事の鮮度上限、data.js に貯める期間
PER_FEED_LIMIT = 40
MAIN_FEED_LIMIT = 60
MAX_AGE_DAYS = 120        # 新規取り込み時に無視する古さ
KEEP_DAYS = 365           # data.js に貯めておく期間（資料化で振り返る用）
MAX_ITEMS = 4000          # 保険。これを超えたら古い順に落とす

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "rss": "http://purl.org/rss/1.0/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)

# フィードの末尾に付く定型文。資料化のときに邪魔になるので落とす。
BOILERPLATE_RE = re.compile(
    r"(Continue reading this article.*$"
    r"|The post .{0,120}? appeared first on .*$"
    r"|Read (?:more|More).{0,40}$"
    r"|続きをみる$|続きを読む$|もっと読む$)", re.S)


def log(msg):
    print(msg, file=sys.stderr)


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def clean_text(html, limit=200):
    if not html:
        return ""
    text = TAG_RE.sub(" ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'")
                .replace("&#x27;", "'"))
    text = WS_RE.sub(" ", text).strip()
    text = BOILERPLATE_RE.sub("", text).strip(" 　…・|-")
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def parse_date(raw):
    """RFC822 / ISO8601 のどちらでも受けて JST の datetime を返す。"""
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def find_text(el, *paths):
    for p in paths:
        found = el.find(p, NS)
        if found is not None:
            if found.text and found.text.strip():
                return found.text.strip()
            href = found.get("href")      # Atom の <link href="...">
            if href:
                return href.strip()
    return ""


def find_thumb(el, body_html):
    for path in ("media:thumbnail", "media:content", "enclosure"):
        found = el.find(path, NS)
        if found is not None:
            url = found.get("url") or (found.text or "").strip()
            if url:
                return url
    m = IMG_RE.search(body_html or "")
    return m.group(1) if m else ""


def parse_feed(xml_bytes):
    """RSS2.0 / Atom / RDF をまとめて正規化する。"""
    root = ET.fromstring(xml_bytes)
    entries = (root.findall(".//item")
               + root.findall(".//rss:item", NS)
               + root.findall(".//atom:entry", NS))
    out = []
    for el in entries:
        title = clean_text(find_text(el, "title", "rss:title", "atom:title"), 300)
        link = find_text(el, "link", "rss:link", "atom:link")
        if not link:
            guid = find_text(el, "guid")
            link = guid if guid.startswith("http") else ""
        if not title or not link:
            continue
        body = find_text(el, "content:encoded", "description", "rss:description",
                         "atom:content", "atom:summary")
        raw_date = find_text(el, "pubDate", "atom:published", "atom:updated", "dc:date")
        out.append({
            "title": title,
            "url": link,
            "date": parse_date(raw_date),
            "summary": clean_text(body, 180),
            "thumb": find_thumb(el, body),
        })
    return out


_ASCII_RE = re.compile(r"^[a-z0-9 .+*-]+$")
_KW_CACHE = {}


def _match(kw, text):
    """英数キーワードは単語境界で判定する（"Fairphone" が "ai" に当たるのを防ぐ）。
    末尾に * を付けたものは語幹一致（"launch*" が launches/launched にも当たる）。"""
    if not _ASCII_RE.match(kw):
        return kw in text
    pat = _KW_CACHE.get(kw)
    if pat is None:
        if kw.endswith("*"):
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(kw[:-1]) + r"[a-z]*")
        else:
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
        _KW_CACHE[kw] = pat
    return pat.search(text) is not None


def _any(words, text):
    return any(_match(w, text) for w in words)


def passes_filter(item, mode):
    if not mode:
        return True
    text = (item["title"] + " " + item["summary"]).lower()

    if mode == "ai":
        return _any(AI_KEYWORDS, text)
    if mode == "product":
        return _any(PRODUCT_KEYWORDS, text)

    if mode == "launch":
        # 9to5Google のような一般Googleニュース向け。
        # 「AI or 新デバイスの話」かつ「新しく発表・提供開始された」ものだけ通す。
        # 日々のPixel小改良、セール、レビュー、噂は落とす。
        if _any(LAUNCH_EXCLUDE, text):
            return False
        return _any(LAUNCH_SUBJECT, text) and _any(LAUNCH_ANNOUNCE, text)

    raise ValueError("unknown filter mode: " + str(mode))


def topics_for(item, axis):
    text = (item["title"] + " " + item["summary"]).lower()
    rules = TOPIC_RULES_BY_AXIS[axis]
    tags = [name for name, kws in rules if any(_match(k, text) for k in kws)]
    return tags[:3] or ["その他"]


def url_key(url):
    return url.split("?")[0].split("#")[0].rstrip("/").lower()


def title_key(title):
    return re.sub(r"[\s　【】\[\]|｜:：-]", "", title).lower()[:45]


def load_existing():
    """前回の data.js を読んで items を返す（累積マージ用）。

    貯めたデータにも現在のフィルタとトピック規則を再適用する。こうしないと、
    フィルタを厳しくしても過去に取り込んだノイズが永久に残ってしまう。
    """
    if not os.path.exists(OUT_PATH):
        return []
    try:
        txt = open(OUT_PATH, encoding="utf-8").read()
        data = json.loads(txt[txt.index("{"):txt.rindex(";")])
    except (OSError, ValueError):
        log("!! data.js を読めなかったので新規作成扱いにする")
        return []

    by_id = {f["id"]: f for f in FEEDS}
    items, dropped = [], 0
    for it in data.get("items", []):
        it["date"] = parse_date(it.get("date"))
        it.setdefault("axis", "ai")          # 2軸化より前のデータへの後方互換
        feed = by_id.get(it.get("source"))
        if feed:
            if not passes_filter(it, feed["filter"]):
                dropped += 1
                continue
            it["axis"] = feed["axis"]        # 軸の付け替えにも追随させる
            it["kind"] = feed["kind"]
            it["sourceName"] = feed["name"]
            it["topics"] = topics_for(it, feed["axis"])
        items.append(it)

    if dropped:
        log("--  既存{}件が現在のフィルタに合わないため除去".format(dropped))
    return items


def main():
    now = datetime.now(JST)
    cutoff_new = now - timedelta(days=MAX_AGE_DAYS)
    cutoff_keep = now - timedelta(days=KEEP_DAYS)

    existing = load_existing()
    fresh_items = []
    stats = []

    for feed in FEEDS:
        axis = feed["axis"]
        try:
            parsed = parse_feed(fetch(feed["url"]))
        except (urllib.error.URLError, ET.ParseError, OSError) as e:
            log("NG  {:<22} {}".format(feed["name"], e))
            stats.append({"id": feed["id"], "name": feed["name"], "axis": axis,
                          "kind": feed["kind"], "count": 0, "ok": False})
            continue

        limit = MAIN_FEED_LIMIT if feed["kind"] == "main" else PER_FEED_LIMIT
        # 投稿頻度が低いソースは max_age で鮮度上限を個別に緩められる
        cut = now - timedelta(days=feed.get("max_age", MAX_AGE_DAYS))
        picked = [it for it in parsed if passes_filter(it, feed["filter"])]
        picked = [it for it in picked if it["date"] and it["date"] >= cut]
        picked.sort(key=lambda x: x["date"], reverse=True)

        for it in picked[:limit]:
            # Google News のタイトルは末尾に " - 媒体名" が付くので落とす
            if feed.get("clean_title") == "gnews":
                it["title"] = re.sub(r"\s+-\s+[^\s-]{1,40}$", "", it["title"]).strip()
            it["source"] = feed["id"]
            it["sourceName"] = feed["name"]
            it["axis"] = axis
            it["kind"] = feed["kind"]
            it["weekly"] = feed["id"] == "agilabo" and "週刊AI" in it["title"]
            it["topics"] = topics_for(it, axis)
            fresh_items.append(it)

        log("OK  {:<22} {:>3}件 / 全{:>4}件  [{}]".format(
            feed["name"], min(len(picked), limit), len(parsed), AXIS_LABEL[axis]))
        stats.append({"id": feed["id"], "name": feed["name"], "axis": axis,
                      "kind": feed["kind"], "count": min(len(picked), limit), "ok": True})

    # Claude が web 検索で拾った補完記事
    if os.path.exists(EXTRA_PATH):
        with open(EXTRA_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        for it in extra:
            it.setdefault("source", "pickup")
            it.setdefault("sourceName", it.get("sourceName") or "ピックアップ")
            it.setdefault("axis", "ai")
            it.setdefault("kind", "pickup")
            it.setdefault("summary", "")
            it.setdefault("thumb", "")
            it["weekly"] = False
            it["date"] = parse_date(it.get("date"))
            it["topics"] = it.get("topics") or topics_for(it, it["axis"])
            fresh_items.append(it)
        log("OK  {:<22} {:>3}件".format("ピックアップ", len(extra)))

    # --- 累積マージ: 既存 + 新着。同じURL/タイトルなら新着側で上書き ---
    merged = {}
    order = []
    for it in existing + fresh_items:
        k = url_key(it["url"])
        if k not in merged:
            order.append(k)
        merged[k] = it            # 後勝ち = 新着がメタ情報を更新する

    items = [merged[k] for k in order]

    # タイトル重複（同じ記事が別URLで流れてくるケース）を除去。メインソース優先。
    items.sort(key=lambda x: (x["kind"] != "main",
                              -(x["date"].timestamp() if x["date"] else 0)))
    seen_title, deduped = set(), []
    for it in items:
        tk = (it["axis"], title_key(it["title"]))
        if tk in seen_title:
            continue
        seen_title.add(tk)
        deduped.append(it)

    # 保存期間で間引き
    kept = [it for it in deduped if not it["date"] or it["date"] >= cutoff_keep]
    kept.sort(key=lambda x: x["date"].timestamp() if x["date"] else 0, reverse=True)
    if len(kept) > MAX_ITEMS:
        kept = kept[:MAX_ITEMS]

    added = len(kept) - len(existing)
    for it in kept:
        it["date"] = it["date"].isoformat() if it["date"] else ""

    payload = {
        "updatedAt": now.isoformat(),
        "sources": stats,
        "axes": [{"id": "ai", "label": AXIS_LABEL["ai"],
                  "topics": [n for n, _ in AI_TOPIC_RULES] + ["その他"]},
                 {"id": "product", "label": AXIS_LABEL["product"],
                  "topics": [n for n, _ in PRODUCT_TOPIC_RULES] + ["その他"]}],
        "items": kept,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("// AI Radar データ - build.py が自動生成。手で編集しない。\n")
        f.write("window.AIRADAR_DATA = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")

    n_ai = sum(1 for i in kept if i["axis"] == "ai")
    n_pr = sum(1 for i in kept if i["axis"] == "product")
    n_wk = sum(1 for i in kept if i["weekly"])
    log("\n=> {}".format(OUT_PATH))
    log("   計{}件（AI {} / プロダクト {} / うち週刊AI {}回）、前回から{:+d}件".format(
        len(kept), n_ai, n_pr, n_wk, added))


if __name__ == "__main__":
    main()
