import { state } from "./state.js";
import { el } from "./utils.js";

// 会派名 → CSS変数名(--kaiha-*) のマッピング
// 一致しないものは default 色になる
const KAIHA_COLOR_VAR = {
  "自由創政": "--kaiha-jiyusosei",
  "信風": "--kaiha-shinpu",
  "よなご・未来": "--kaiha-yonagomirai",
  "公明党議員団": "--kaiha-komei",
  "無所属": "--kaiha-mushozoku",
  "日本共産党米子市議団": "--kaiha-kyosanto",
  "新ファミリア": "--kaiha-familia",
};

// 会派カードを並べる順番(人数の多い順 + 末尾に無所属/新ファミリア)
const KAIHA_ORDER = [
  "自由創政",
  "信風",
  "よなご・未来",
  "公明党議員団",
  "日本共産党米子市議団",
  "新ファミリア",
  "無所属",
];

// 委員会ビューの並び順
const COMMITTEE_ORDER = [
  "議会運営",
  "総務政策",
  "民生教育",
  "都市経済",
  "予算決算",
  "基地問題等調査特別",
  "原子力発電・エネルギー問題等調査特別",
];

// 委員会種別 → CSS変数
const COMMITTEE_TYPE_COLOR_VAR = {
  "議会運営": "--committee-giun",
  "常任": "--committee-jonin",
  "特別": "--committee-tokubetsu",
};

// 役職の並び順(同役職内は kana 五十音順)
const ROLE_ORDER = { "委員長": 0, "副委員長": 1, "委員": 2 };

// 当選回数ビューの表示範囲(空のバケットも表示する)
const TERM_RANGE = [1, 2, 3, 4, 5, 6];

// リンク種別の表示順とラベル/アイコン。
// アイコンは現状 emoji。将来 SVG に差し替える場合は icon の値を
// <svg> の HTML 文字列にし、renderMemberCard 側を innerHTML 対応に
// 切り替える(CSS の .member-link-icon は wrapper のみを担当)。
const LINK_TYPES = [
  { key: "official_site",    icon: "🌐", label: "公式サイト" },
  { key: "blog",             icon: "📝", label: "ブログ" },
  { key: "twitter",          icon: "𝕏",  label: "X (旧 Twitter)" },
  { key: "facebook",         icon: "Ⓕ", label: "Facebook" },
  { key: "instagram",        icon: "📷", label: "Instagram" },
  { key: "youtube",          icon: "▶",  label: "YouTube" },
  { key: "election_dot_com", icon: "🗳", label: "選挙ドットコム" },
];

function kaihaColor(kaiha) {
  const v = KAIHA_COLOR_VAR[kaiha] || "--kaiha-default";
  return `var(${v})`;
}

function committeeColor(type) {
  const v = COMMITTEE_TYPE_COLOR_VAR[type] || "--kaiha-default";
  return `var(${v})`;
}

function groupByKaiha(members) {
  const map = new Map();
  for (const m of members) {
    const key = m.kaiha || "(未分類)";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(m);
  }
  // ソート: KAIHA_ORDER に沿って並べ、未指定は末尾にABC順
  const ordered = [];
  for (const k of KAIHA_ORDER) {
    if (map.has(k)) ordered.push([k, map.get(k)]);
  }
  for (const [k, v] of map.entries()) {
    if (!KAIHA_ORDER.includes(k)) ordered.push([k, v]);
  }
  return ordered;
}

function groupByCommittee(members) {
  const map = new Map();
  for (const m of members) {
    for (const c of m.committees || []) {
      if (!map.has(c.name)) {
        map.set(c.name, { type: c.type, entries: [] });
      }
      map.get(c.name).entries.push({ member: m, role: c.role });
    }
  }
  for (const group of map.values()) {
    group.entries.sort((a, b) => {
      const ra = ROLE_ORDER[a.role] ?? 99;
      const rb = ROLE_ORDER[b.role] ?? 99;
      if (ra !== rb) return ra - rb;
      return (a.member.kana || "").localeCompare(b.member.kana || "", "ja");
    });
  }
  const ordered = [];
  for (const name of COMMITTEE_ORDER) {
    if (map.has(name)) ordered.push([name, map.get(name)]);
  }
  for (const [name, group] of map.entries()) {
    if (!COMMITTEE_ORDER.includes(name)) ordered.push([name, group]);
  }
  return ordered;
}

function groupByTermCount(members) {
  const map = new Map();
  for (const t of TERM_RANGE) map.set(t, []);
  for (const m of members) {
    const t = m.term_count;
    if (typeof t !== "number") continue;
    if (!map.has(t)) map.set(t, []);
    map.get(t).push(m);
  }
  for (const list of map.values()) {
    list.sort((a, b) =>
      (a.kana || "").localeCompare(b.kana || "", "ja"),
    );
  }
  return [...map.entries()].sort((a, b) => a[0] - b[0]);
}

function renderMemberCard(m) {
  const colorStyle = `--kaiha-color: ${kaihaColor(m.kaiha)};`;

  // 写真
  const photo = el("img", {
    class: "member-photo",
    src: m.photo_url || "",
    alt: m.name,
    loading: "lazy",
    referrerpolicy: "no-referrer",
  });
  photo.addEventListener("error", () => {
    photo.style.visibility = "hidden";
  });

  // 役職バッジ(議長・副議長 + 委員長・副委員長)
  const positionBadges = [];
  for (const p of m.positions || []) {
    positionBadges.push(el("span", { class: "badge is-position" }, p));
  }
  for (const c of m.committees || []) {
    if (c.role === "委員長") {
      positionBadges.push(
        el("span", { class: "badge is-chair" }, `${c.name}委員長`),
      );
    } else if (c.role === "副委員長") {
      positionBadges.push(
        el("span", { class: "badge is-vice" }, `${c.name}副委員長`),
      );
    }
  }

  // 委員会リスト(委員のみ。委員長/副委員長はバッジ側に出している)
  const committeeItems = (m.committees || [])
    .filter((c) => c.role === "委員")
    .map((c) => el("li", {}, `${c.name}委員（${c.type}）`));

  // リンク群(member_links.json から)
  const linkData = (state.links[m.id] && state.links[m.id].links) || {};
  const linkNodes = LINK_TYPES.filter((t) => linkData[t.key]).map((t) =>
    el(
      "a",
      {
        class: `member-link member-link--${t.key}`,
        href: linkData[t.key],
        target: "_blank",
        rel: "noopener",
        title: t.label,
        "aria-label": t.label,
      },
      [
        el(
          "span",
          { class: "member-link-icon", "aria-hidden": "true" },
          t.icon,
        ),
      ],
    ),
  );

  return el("article", { class: "member-card", style: colorStyle }, [
    el("div", { class: "member-head" }, [
      photo,
      el("div", { class: "member-name-block" }, [
        el("p", { class: "member-name" }, m.name),
        el("p", { class: "member-kana" }, m.kana || ""),
        el(
          "p",
          { class: "member-term" },
          `当選 ${m.term_count ?? "?"} 回`,
        ),
      ]),
    ]),
    positionBadges.length
      ? el("div", { class: "member-positions" }, positionBadges)
      : null,
    committeeItems.length
      ? el("ul", { class: "member-committees" }, committeeItems)
      : null,
    linkNodes.length
      ? el("div", { class: "member-links" }, linkNodes)
      : null,
  ]);
}

export function renderKaihaView(root, members) {
  root.innerHTML = "";
  const grouped = groupByKaiha(members);
  for (const [kaiha, list] of grouped) {
    const headerStyle = `--kaiha-color: ${kaihaColor(kaiha)};`;
    const group = el("section", { class: "kaiha-group" }, [
      el("div", { class: "kaiha-header", style: headerStyle }, [
        el("h2", { class: "kaiha-name" }, kaiha),
        el("span", { class: "kaiha-count" }, `${list.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        list.map(renderMemberCard),
      ),
    ]);
    root.appendChild(group);
  }
}

export function renderCommitteeView(root, members) {
  root.innerHTML = "";
  const grouped = groupByCommittee(members);
  for (const [name, group] of grouped) {
    const headerStyle = `--committee-color: ${committeeColor(group.type)};`;
    const note = name === "予算決算"
      ? el(
          "p",
          { class: "committee-note" },
          "※全議員が所属。正副委員長のみ表示しています。",
        )
      : null;
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, name),
        el("span", { class: "committee-type-badge" }, group.type),
        el("span", { class: "committee-count" }, `${group.entries.length}人`),
      ]),
      note,
      el(
        "div",
        { class: "member-grid" },
        group.entries.map(({ member }) => renderMemberCard(member)),
      ),
    ]);
    root.appendChild(section);
  }
}

export function renderRoleView(root, members) {
  root.innerHTML = "";

  // 第1セクション: 議長・副議長(金色アクセント)
  const heads = members
    .filter((m) =>
      (m.positions || []).some((p) => p === "議長" || p === "副議長"),
    )
    .sort((a, b) => {
      const ra = (a.positions || []).includes("議長") ? 0 : 1;
      const rb = (b.positions || []).includes("議長") ? 0 : 1;
      return ra - rb;
    });

  if (heads.length > 0) {
    const headerStyle = "--committee-color: var(--position-gold);";
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, "議長・副議長"),
        el("span", { class: "committee-count" }, `${heads.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        heads.map(renderMemberCard),
      ),
    ]);
    root.appendChild(section);
  }

  // 第2〜N セクション: 各委員会の委員長/副委員長(委員会ビューと同じ並び)
  const grouped = groupByCommittee(members);
  for (const [name, group] of grouped) {
    const leaders = group.entries.filter(
      (e) => e.role === "委員長" || e.role === "副委員長",
    );
    if (leaders.length === 0) continue;
    const headerStyle = `--committee-color: ${committeeColor(group.type)};`;
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, name),
        el("span", { class: "committee-type-badge" }, group.type),
        el("span", { class: "committee-count" }, `${leaders.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        leaders.map(({ member }) => renderMemberCard(member)),
      ),
    ]);
    root.appendChild(section);
  }
}

export function renderTermView(root, members) {
  root.innerHTML = "";
  const grouped = groupByTermCount(members);
  const total = members.length;
  const isFiltered = state.query.trim().length > 0;

  for (const [term, list] of grouped) {
    const count = list.length;
    // 検索中は空バケットを非表示(分布のギャップは検索なし時のみ表示)
    if (isFiltered && count === 0) continue;
    const pctOfTotal =
      total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";

    const section = el("section", { class: "term-group" }, [
      el("div", { class: "term-header" }, [
        el("span", { class: "term-label" }, `${term}回`),
        el(
          "span",
          { class: "term-count" },
          count > 0 ? `${count}人 (${pctOfTotal}%)` : "該当なし",
        ),
      ]),
      count > 0
        ? el(
            "div",
            { class: "member-grid" },
            list.map(renderMemberCard),
          )
        : null,
    ]);
    root.appendChild(section);
  }
}
