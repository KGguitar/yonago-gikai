"""member_links.json と members.json の整合性チェッカー / 同期ツール。

- チェックのみ:
    python scripts/sync_links.py
- 不足エントリを自動追加して保存:
    python scripts/sync_links.py --write

孤児エントリ(member_links.json にあるが members.json にいない)は警告のみで
自動削除しない。手動で確認してから削除すること(議員入れ替わり時の安全弁)。

差分があれば exit code 1(CIで使える)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMBERS_PATH = REPO_ROOT / "docs" / "data" / "members.json"
LINKS_PATH = REPO_ROOT / "docs" / "data" / "member_links.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="不足エントリを追加して member_links.json を上書き",
    )
    args = parser.parse_args()

    members = load_json(MEMBERS_PATH, [])
    links = load_json(LINKS_PATH, {})

    if not members:
        print(f"ERROR: {MEMBERS_PATH} が見つからないか空です。", file=sys.stderr)
        return 2

    member_ids = {m["id"]: m["name"] for m in members if m.get("id")}
    link_ids = set(links.keys())

    missing = [mid for mid in member_ids if mid not in link_ids]
    orphans = [lid for lid in link_ids if lid not in member_ids]

    print(f"members.json: {len(member_ids)} 議員")
    print(f"member_links.json: {len(link_ids)} エントリ")

    if missing:
        print(f"\n[追加が必要] {len(missing)} 名:")
        for mid in missing:
            print(f"  + {mid}  ({member_ids[mid]})")

    if orphans:
        print(f"\n[孤児エントリ(議員側にいない)] {len(orphans)} 件:")
        for lid in orphans:
            entry = links[lid]
            name = (
                entry.get("_name", "?") if isinstance(entry, dict) else "?"
            )
            print(f"  - {lid}  ({name})")
        print("  (自動削除しません。確認の上、手動で削除してください)")

    if not missing and not orphans:
        print("\nOK: 整合しています。")
        return 0

    if args.write:
        # 不足分を追加
        for mid in missing:
            links[mid] = {"_name": member_ids[mid], "links": {}}
        # members.json の順に並べ直し、孤児は末尾に残す
        ordered: dict = {}
        for m in members:
            mid = m.get("id")
            if mid and mid in links:
                ordered[mid] = links[mid]
        for lid in orphans:
            ordered[lid] = links[lid]

        LINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LINKS_PATH.open("w", encoding="utf-8") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(
            f"\nwrote {LINKS_PATH} "
            f"(追加: {len(missing)}件, 孤児: {len(orphans)}件はそのまま)"
        )
        return 0

    print("\n→ --write を付けて再実行すると、不足分を追加します。")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
