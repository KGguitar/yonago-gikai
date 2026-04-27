"""米子市の新着情報スクレイパー (Phase 2.1.4)

ソース:
  - info  : 市政情報の新着       https://www.city.yonago.lg.jp/info/
  - iken  : 市民意見募集(パブコメ) https://www.city.yonago.lg.jp/14752.htm
            (33792.htm はインデックス頁で実体無し。14752.htm を実データソースに採用)

将来:
  - 告示・公示等 (1049.htm) は PDF 集約形式のため Phase 3 で別設計として扱う

出力: docs/data/news.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

USER_AGENT = (
    "yonago-gikai-scraper/0.1 "
    "(+https://github.com/; civic-tech; contact: tamaken.lespo@gmail.com)"
)
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 2

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "docs" / "data" / "news.json"
SITE_BASE = "https://www.city.yonago.lg.jp"

# ソース定義
SOURCES: dict[str, dict] = {
    "info": {
        "url": f"{SITE_BASE}/info/",
        "category": "市政情報",
    },
    "iken": {
        "url": f"{SITE_BASE}/14752.htm",
        "category": "市民意見募集",
    },
}

ITEM_ID_PATTERN = re.compile(r"/item/(\d+)\.htm")
DATE_PATTERN = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")


def fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace(" ", " ").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_info_items(html: str, now_iso: str) -> list[dict]:
    """市政情報の新着 (info ソース) をパース。"""
    return _parse_pickup_section(html, source="info", now_iso=now_iso)


def parse_iken_items(html: str, now_iso: str) -> list[dict]:
    """市民意見募集 (iken ソース、パブリックコメント頁) をパース。
    info と同じ div.PickUp_info 構造を利用。
    """
    return _parse_pickup_section(html, source="iken", now_iso=now_iso)


def _parse_pickup_section(
    html: str, source: str, now_iso: str
) -> list[dict]:
    """PickUp_info セクション (div.PickUp_info > ul > li) を共通パース。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="PickUp_info")
    if not container:
        raise RuntimeError(
            f"div.PickUp_info が見つかりません (source={source}; "
            "構造変化の可能性)"
        )

    category = SOURCES[source]["category"]
    items: list[dict] = []
    for li in container.find_all("li"):
        item = _parse_pickup_li(li, source, category, now_iso)
        if item:
            items.append(item)
    return items


def _parse_pickup_li(
    li: Tag, source: str, category: str, now_iso: str
) -> dict | None:
    # 日付
    date_span = li.find("span", class_="CreatedDate")
    if not date_span:
        return None
    m = DATE_PATTERN.search(date_span.get_text())
    if not m:
        return None
    date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # タイトルとリンク
    a = li.find("a")
    if not a:
        return None
    href = a.get("href", "")
    title = normalize_text(a.get_text())
    m_id = ITEM_ID_PATTERN.search(href)
    if not m_id:
        return None
    itemid = m_id.group(1)
    url = f"{SITE_BASE}/item/{itemid}.htm"

    # 概要(空なら null に正規化)
    summary_div = li.find("div", class_="Summary")
    summary_text = normalize_text(summary_div.get_text()) if summary_div else ""
    summary = summary_text if summary_text else None

    return {
        "id": f"{source}-{date_str}-{itemid}",
        "date": date_str,
        "title": title,
        "url": url,
        "category": category,
        "summary": summary,
        "source": source,
        "scraped_at": now_iso,
    }


# ソース → パーサ関数 のディスパッチ
PARSERS = {
    "info": parse_info_items,
    "iken": parse_iken_items,
}


def write_output(items: list[dict], sources_used: list[str]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources_used,
        "items": items,
    }
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {OUT_PATH} ({len(items)} items, sources: {sources_used})")


def main() -> int:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_items: list[dict] = []
    sources_used: list[str] = []

    for source, parser in PARSERS.items():
        url = SOURCES[source]["url"]
        print(f"fetching {url} (source={source}) ...")
        try:
            html = fetch_html(url)
            time.sleep(SLEEP_SECONDS)
            items = parser(html, now_iso)
        except Exception as e:
            # 1ソースの失敗で全体を止めない。WARN にして他ソース続行。
            print(
                f"WARNING: source '{source}' failed: {e}",
                file=sys.stderr,
            )
            continue

        print(f"  parsed {len(items)} items from {source}")
        if len(items) == 0:
            print(
                f"WARNING: source '{source}' returned 0 items "
                "(structure may have changed)",
                file=sys.stderr,
            )
        all_items.extend(items)
        sources_used.append(source)

    # 日付降順で安定化(同日は既存順)
    all_items.sort(key=lambda x: x["date"], reverse=True)

    # 最低件数チェック: 全ソース合算で1件以上(0件ならERR)
    if len(all_items) == 0:
        print(
            "ERROR: parsed 0 items across all sources",
            file=sys.stderr,
        )
        return 1

    print(f"TOTAL: {len(all_items)} items across {len(sources_used)} source(s)")
    write_output(all_items, sources_used)
    return 0


if __name__ == "__main__":
    sys.exit(main())
