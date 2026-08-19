# -*- coding: utf-8 -*-
"""
AI Radar - データ収集スクリプト

AGIラボ「週刊AI」をメインソースに、国内外のAIニュースフィードを横断取得して
data.js（window.AIRADAR_DATA）を生成する。

使い方:
    python C:/Users/S19122/ai-radar/build.py

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
# kind: main=メインソース / jp=国内メディア / global=海外メディア / official=開発元公式
# ai_only: True のフィードは全記事AI関連とみなす。False は AI キーワードで絞り込む。
FEEDS = [
    {"id": "agilabo",   "name": "AGIラボ",            "kind": "main",
     "url": "https://chatgpt-lab.com/rss", "ai_only": True},

    {"id": "itmedia",   "name": "ITmedia AI+",        "kind": "jp",
     "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "ai_only": True},
    {"id": "ainow",     "name": "AINOW",              "kind": "jp",
     "url": "https://ainow.ai/feed/", "ai_only": True},
    {"id": "publickey", "name": "Publickey",          "kind": "jp",
     "url": "https://www.publickey1.jp/atom.xml", "ai_only": False},
    {"id": "zenn",      "name": "Zenn (AI)",          "kind": "jp",
     "url": "https://zenn.dev/topics/ai/feed", "ai_only": True},
    {"id": "ascii",     "name": "ASCII.jp",           "kind": "jp",
     "url": "https://ascii.jp/rss.xml", "ai_only": False},
    {"id": "impress",   "name": "PC Watch",           "kind": "jp",
     "url": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf", "ai_only": False},
    {"id": "xtech",     "name": "日経xTECH",           "kind": "jp",
     "url": "https://xtech.nikkei.com/rss/xtech-it.rdf", "ai_only": False},
    {"id": "gigazine",  "name": "GIGAZINE",           "kind": "jp",
     "url": "https://gigazine.net/news/rss_2.0/", "ai_only": False},
    {"id": "mittr",     "name": "MITTR Japan",        "kind": "jp",
     "url": "https://www.technologyreview.jp/feed/", "ai_only": False},

    {"id": "techcrunch", "name": "TechCrunch AI",     "kind": "global",
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "ai_only": True},
    {"id": "hf",        "name": "Hugging Face",       "kind": "global",
     "url": "https://huggingface.co/blog/feed.xml", "ai_only": True},

    {"id": "openai",    "name": "OpenAI",             "kind": "official",
     "url": "https://openai.com/news/rss.xml", "ai_only": True},
    {"id": "googleai",  "name": "Google AI",          "kind": "official",
     "url": "https://blog.google/technology/ai/rss/", "ai_only": True},
    {"id": "deepmind",  "name": "Google DeepMind",    "kind": "official",
     "url": "https://deepmind.google/blog/rss.xml", "ai_only": True},
]

# ai_only=False のフィードを絞り込むキーワード
AI_KEYWORDS = [
    "ai", "生成ai", "人工知能", "llm", "chatgpt", "gpt", "claude", "gemini",
    "copilot", "openai", "anthropic", "nvidia", "機械学習", "ディープラーニング",
    "エージェント", "agent", "grok", "llama", "深層学習", "推論モデル",
]

# トピックタグの判定ルール（表示順 = 優先度）
TOPIC_RULES = [
    ("モデル",     ["gpt", "claude", "gemini", "llama", "grok", "opus", "sonnet", "haiku",
                    "モデル", "llm", "推論", "o3", "o4", "mistral", "qwen", "deepseek",
                    "ベンチマーク", "benchmark", "model"]),
    ("エージェント", ["エージェント", "agent", "codex", "claude code", "devin", "mcp",
                    "自律", "ワークフロー自動", "cursor", "copilot"]),
    ("画像・音声・動画", ["画像生成", "動画生成", "音声", "sora", "midjourney", "veo",
                    "stable diffusion", "音楽", "image", "video", "voice", "tts"]),
    ("ビジネス・資金", ["資金調達", "買収", "提携", "決算", "ipo", "投資", "billion",
                    "評価額", "funding", "acquire", "パートナーシップ", "億ドル", "兆円"]),
    ("規制・リスク", ["規制", "法案", "ガイドライン", "著作権", "プライバシー", "訴訟",
                    "セキュリティ", "リスク", "regulation", "lawsuit", "安全性", "safety"]),
    ("開発・技術",  ["api", "オープンソース", "oss", "sdk", "実装", "開発者",
                    "open source", "developer", "github", "コード"]),
    ("広告・マーケ", ["広告", "マーケティング", "マーケ", "seo", "検索連動", "ecサイト",
                    "advertis", "marketing", "ブランド"]),
    ("インフラ・半導体", ["gpu", "半導体", "データセンター", "nvidia", "tpu", "チップ",
                    "電力", "chip", "cloud", "クラウド基盤"]),
]

# 1フィードあたりの採用上限と、収録する記事の鮮度上限
PER_FEED_LIMIT = 25
MAIN_FEED_LIMIT = 60      # メインソース（AGIラボ）は多めに残す
MAX_AGE_DAYS = 120

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
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = WS_RE.sub(" ", text).strip()
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
            # Atom の <link href="..."> 形式
            href = found.get("href")
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
    """RSS2.0 / Atom / RDF をまとめて (title, link, date, summary, thumb) に正規化。"""
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


_ASCII_RE = re.compile(r"^[a-z0-9 .+-]+$")
_KW_CACHE = {}


def _match(kw, text):
    """英数キーワードは単語境界で判定する（"Fairphone" が "ai" に当たるのを防ぐ）。"""
    if not _ASCII_RE.match(kw):
        return kw in text
    pat = _KW_CACHE.get(kw)
    if pat is None:
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
        _KW_CACHE[kw] = pat
    return pat.search(text) is not None


def is_ai_related(item):
    text = (item["title"] + " " + item["summary"]).lower()
    return any(_match(kw, text) for kw in AI_KEYWORDS)


def topics_for(item):
    text = (item["title"] + " " + item["summary"]).lower()
    tags = [name for name, kws in TOPIC_RULES if any(_match(k, text) for k in kws)]
    return tags[:3] or ["その他"]


def main():
    all_items = []
    stats = []

    for feed in FEEDS:
        try:
            raw = fetch(feed["url"])
            parsed = parse_feed(raw)
        except (urllib.error.URLError, ET.ParseError, OSError) as e:
            log("NG  {:<14} {}".format(feed["name"], e))
            stats.append({"id": feed["id"], "name": feed["name"], "count": 0, "ok": False})
            continue

        cutoff = datetime.now(JST) - timedelta(days=MAX_AGE_DAYS)
        limit = MAIN_FEED_LIMIT if feed["kind"] == "main" else PER_FEED_LIMIT

        fresh = [it for it in parsed
                 if (not feed["ai_only"] and is_ai_related(it)) or feed["ai_only"]]
        fresh = [it for it in fresh if it["date"] and it["date"] >= cutoff]
        fresh.sort(key=lambda x: x["date"], reverse=True)

        for it in fresh[:limit]:
            it["source"] = feed["id"]
            it["sourceName"] = feed["name"]
            it["kind"] = feed["kind"]
            it["weekly"] = feed["id"] == "agilabo" and "週刊AI" in it["title"]
            it["topics"] = topics_for(it)
            all_items.append(it)

        kept = min(len(fresh), limit)
        log("OK  {:<14} {:>3}件 / 全{:>4}件".format(feed["name"], kept, len(parsed)))
        stats.append({"id": feed["id"], "name": feed["name"], "kind": feed["kind"],
                      "count": kept, "ok": True})

    # Claude が web 検索で拾った補完記事をマージ
    if os.path.exists(EXTRA_PATH):
        with open(EXTRA_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        for it in extra:
            it.setdefault("source", "pickup")
            it.setdefault("sourceName", it.get("sourceName") or "ピックアップ")
            it.setdefault("kind", "pickup")
            it.setdefault("summary", "")
            it.setdefault("thumb", "")
            it["weekly"] = False
            it["date"] = parse_date(it.get("date"))
            it["topics"] = it.get("topics") or topics_for(it)
            all_items.append(it)
        log("OK  {:<14} {:>3}件".format("ピックアップ", len(extra)))

    # URL / タイトルで重複排除（先勝ち＝メインソース優先）
    all_items.sort(key=lambda x: (x["source"] != "agilabo",
                                  -(x["date"].timestamp() if x["date"] else 0)))
    seen_url, seen_title, deduped = set(), set(), []
    for it in all_items:
        key_url = it["url"].split("?")[0].rstrip("/")
        key_title = re.sub(r"[\s　【】\[\]|｜]", "", it["title"])[:40]
        if key_url in seen_url or key_title in seen_title:
            continue
        seen_url.add(key_url)
        seen_title.add(key_title)
        deduped.append(it)

    deduped.sort(key=lambda x: x["date"].timestamp() if x["date"] else 0, reverse=True)

    for it in deduped:
        it["date"] = it["date"].isoformat() if it["date"] else ""

    payload = {
        "updatedAt": datetime.now(JST).isoformat(),
        "sources": stats,
        "topics": [name for name, _ in TOPIC_RULES] + ["その他"],
        "items": deduped,
    }

    body = json.dumps(payload, ensure_ascii=False, indent=1)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("// AI Radar データ - build.py が自動生成。手で編集しない。\n")
        f.write("window.AIRADAR_DATA = " + body + ";\n")

    weekly = sum(1 for i in deduped if i["weekly"])
    log("\n=> {} に {}件を書き出し（うち週刊AI {}回）".format(OUT_PATH, len(deduped), weekly))


if __name__ == "__main__":
    main()
