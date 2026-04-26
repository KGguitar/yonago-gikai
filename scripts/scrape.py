"""米子市議会 議員一覧スクレイパー (Phase 1.1)

ソース: https://www.city.yonago.lg.jp/2919.htm
出力: docs/data/members.json, docs/data/meta.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

SOURCE_URL = "https://www.city.yonago.lg.jp/2919.htm"
USER_AGENT = (
    "yonago-gikai-scraper/0.1 "
    "(+https://github.com/; civic-tech; contact: tamaken.lespo@gmail.com)"
)
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 2

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "data"

# 委員会の正規化辞書: 出現しうる名前 → (正規名, 種別)
COMMITTEE_TYPES: dict[str, str] = {
    "総務政策": "常任",
    "民生教育": "常任",
    "都市経済": "常任",
    "予算決算": "常任",
    "議会運営": "議会運営",
    "基地問題等調査特別": "特別",
    "原子力発電・エネルギー問題等調査特別": "特別",
}

# 議会全体の役職（委員会の役割ではないもの）
GLOBAL_POSITIONS = ("議長", "副議長")

# ヘボン式かな→ローマ字。長音記号「ー」と長音「う/お」は単純に各文字を変換するのみ
# (例: ようこ → youko, りゅうじ → ryuuji)
HIRAGANA_TO_ROMAJI: dict[str, str] = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "wo", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
}
COMPOUND_HIRAGANA: dict[str, str] = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
}


def make_id(kana: str) -> str:
    """ふりがな → ID(ヘボン式ローマ字スラッグ)。

    例: "あだち たかし" → "adachi-takashi"
        "とだ りゅうじ" → "toda-ryuuji"
        "わたなべ じょうじ" → "watanabe-jouji"

    ルール:
      - 拗音(きゃ等)は2文字を1音節として処理
      - 長音記号「ー」は無視
      - 半角/全角空白は "-" に変換
      - 不明文字はスキップ
    """
    if not kana:
        return ""
    s = kana.strip()
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in (" ", "　"):
            out.append("-")
            i += 1
            continue
        if i + 1 < len(s) and s[i : i + 2] in COMPOUND_HIRAGANA:
            out.append(COMPOUND_HIRAGANA[s[i : i + 2]])
            i += 2
            continue
        if ch in HIRAGANA_TO_ROMAJI:
            out.append(HIRAGANA_TO_ROMAJI[ch])
        # それ以外(「ー」や未知文字)は無視
        i += 1
    return "".join(out)


def assign_unique_ids(members: list[dict]) -> None:
    """同一IDが衝突した場合、2人目以降に -2, -3 を付与。"""
    counts: dict[str, int] = {}
    for m in members:
        base = m.get("id", "")
        if not base:
            continue
        n = counts.get(base, 0) + 1
        counts[base] = n
        if n > 1:
            print(
                f"WARNING: id collision '{base}' for {m['name']}, "
                f"renaming to '{base}-{n}'",
                file=sys.stderr,
            )
            m["id"] = f"{base}-{n}"


def fetch_html(url: str) -> str:
    """対象URLを取得してUTF-8テキストを返す。"""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    # 明示的にUTF-8を強制（メタタグでも宣言されている）
    resp.encoding = "utf-8"
    return resp.text


def normalize_text(s: str) -> str:
    """全角/半角空白、NBSP、改行をまとめて正規化。"""
    if s is None:
        return ""
    s = s.replace(" ", " ")  # NBSP
    s = s.replace("　", " ")  # 全角スペース
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def cell_to_lines(td: Tag) -> list[str]:
    """<td>の中身を <br> と <p> で改行分割し、テキスト行のリストにする。"""
    # <br> を改行マーカーに置換
    for br in td.find_all("br"):
        br.replace_with("\n")
    # <p> の前後にも改行を挟む
    for p in td.find_all("p"):
        p.insert_before(NavigableString("\n"))
        p.insert_after(NavigableString("\n"))
    # 「(」「)」だけが残る ruby のフォールバック rp は削除（ふりがな以外の場面でノイズになる）
    raw = td.get_text("")
    lines = [normalize_text(line) for line in raw.split("\n")]
    return [line for line in lines if line]


def parse_member_cell(td: Tag, photo_url: str | None) -> dict | None:
    """議員1人分の <td> をパースして dict を返す。"""
    # 氏名: <strong> の中身
    strong = td.find("strong")
    if not strong:
        return None
    name = normalize_text(strong.get_text())

    # ふりがな: 氏名直下の <ruby> の <rt>
    kana = ""
    ruby = strong.find_parent("ruby")
    if ruby:
        rt = ruby.find("rt")
        if rt:
            kana = normalize_text(rt.get_text())

    lines = cell_to_lines(td)

    # 行ごとに分類
    positions: list[str] = []
    committees: list[dict] = []
    kaiha = ""
    term_count: int | None = None

    for line in lines:
        # 氏名行（ふりがな込み）はスキップ
        if name and name in line and (kana == "" or kana in line):
            continue
        if name and line.startswith(name):
            continue

        # 当選回数
        m = re.search(r"当選回数[：:]\s*(\d+)\s*回", line)
        if m:
            term_count = int(m.group(1))
            continue

        # 会派
        m = re.match(r"^会派[：:]\s*(.+?)\s*$", line)
        if m:
            kaiha = normalize_text(m.group(1))
            # ふりがなが残っていれば剥がす（「自由創政 じゆうそうせい」のような場合）
            kaiha = strip_trailing_kana(kaiha)
            continue

        # 「無所属」単独行
        if line == "無所属":
            kaiha = "無所属"
            continue

        # 「呼称：xxx」（森谷議員のケース） → 会派扱い
        m = re.match(r"^呼称[：:]\s*(.+?)\s*$", line)
        if m:
            kaiha = strip_trailing_kana(normalize_text(m.group(1)))
            continue

        # 議長・副議長
        if line in GLOBAL_POSITIONS:
            positions.append(line)
            continue

        # 委員会・役職
        committee = match_committee(line)
        if committee:
            committees.append(committee)
            continue

        # 想定外行はそのまま捨てる（デバッグ時のみ表示）
        # print(f"[skip] {name}: {line!r}", file=sys.stderr)

    return {
        "id": make_id(kana),
        "name": name,
        "kana": kana,
        "kaiha": kaiha,
        "term_count": term_count,
        "positions": positions,
        "committees": committees,
        "photo_url": photo_url,
    }


def strip_trailing_kana(s: str) -> str:
    """「自由創政 じゆうそうせい」のように末尾にふりがなが残った場合に取り除く。"""
    # ひらがなだけの末尾語を切り落とす
    return re.sub(r"\s+[ぁ-ゖー]+$", "", s).strip()


def match_committee(line: str) -> dict | None:
    """「○○委員長」「○○副委員長」「○○委員」を委員会dictに変換。"""
    # 副委員長 → 委員長 → 委員 の順（長いものから）
    for suffix, role in (("副委員長", "副委員長"), ("委員長", "委員長"), ("委員", "委員")):
        if line.endswith(suffix):
            base = line[: -len(suffix)]
            base = normalize_text(base)
            if base in COMMITTEE_TYPES:
                return {
                    "name": base,
                    "role": role,
                    "type": COMMITTEE_TYPES[base],
                }
            # 未知の委員会名でも記録しておく
            if base:
                return {"name": base, "role": role, "type": "不明"}
    return None


def absolute_url(src: str | None) -> str | None:
    if not src:
        return None
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return "https://www.city.yonago.lg.jp" + src
    return src


def parse_members(html: str) -> list[dict]:
    """ページ全体から議員リストを抽出。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"summary": "議員名簿"})
    if not table:
        raise RuntimeError("議員名簿テーブルが見つかりません")

    members: list[dict] = []
    for tr in table.find_all("tr"):
        # 区切り行（spacer + colspan=2）はスキップ
        if tr.find("td", attrs={"colspan": "2"}):
            continue

        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue

        # tds は [写真, 本文, (rowspanのspacer), 写真, 本文] の最大5要素
        # 本文セルだけ抜き出す: 直前のtdに <img> があり、自分は <strong> を持つ
        i = 0
        while i < len(tds):
            td = tds[i]
            img = td.find("img")
            # rowspan で1x1の spacer.gif が入っているセルは飛ばす
            if (
                img
                and img.get("src", "").endswith("spacer.gif")
                and td.get("rowspan")
            ):
                i += 1
                continue

            # 写真セル + 本文セルのペアを期待
            if img and i + 1 < len(tds) and tds[i + 1].find("strong"):
                photo_url = absolute_url(img.get("src"))
                member = parse_member_cell(tds[i + 1], photo_url)
                if member:
                    members.append(member)
                i += 2
            else:
                i += 1

    return members


def write_outputs(members: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    members_path = OUT_DIR / "members.json"
    with members_path.open("w", encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, indent=2)

    meta = {
        "source_url": SOURCE_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "member_count": len(members),
    }
    meta_path = OUT_DIR / "meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"wrote {members_path} ({len(members)} members)")
    print(f"wrote {meta_path}")


def main() -> int:
    print(f"fetching {SOURCE_URL} ...")
    html = fetch_html(SOURCE_URL)
    time.sleep(SLEEP_SECONDS)  # 礼儀的なインターバル

    members = parse_members(html)
    assign_unique_ids(members)
    print(f"parsed {len(members)} members")

    # 致命的: 議員数が極端に少ない = 構造変化やパース破綻の可能性。
    # 異常データで上書きしないよう中断する。
    if len(members) < 10:
        print(
            f"ERROR: parsed only {len(members)} members; aborting "
            "(source page structure may have changed)",
            file=sys.stderr,
        )
        return 1

    # 想定値からのズレは警告のみ(議員入れ替わりなど正常な変動もある)
    if len(members) != 26:
        print(
            f"WARNING: expected 26 members, got {len(members)}",
            file=sys.stderr,
        )

    write_outputs(members)
    return 0


if __name__ == "__main__":
    sys.exit(main())
