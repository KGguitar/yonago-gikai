import { state } from "./state.js";

export function matchesQuery(member, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  const fields = [
    member.name || "",
    member.kana || "",
    member.kaiha || "",
    ...(member.committees || []).map((c) => c.name || ""),
  ];
  return fields.some((f) => f.toLowerCase().includes(q));
}

export function filteredMembers() {
  const q = state.query.trim();
  if (!q) return state.members;
  return state.members.filter((m) => matchesQuery(m, q));
}

export function matchesNewsItem(item, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  const fields = [
    item.title || "",
    item.summary || "",
    item.category || "",
  ];
  return fields.some((f) => f.toLowerCase().includes(q));
}

export function filteredNewsItems() {
  if (!state.news || !Array.isArray(state.news.items)) return [];
  let items = state.news.items;
  items = items.filter((it) => state.activeSources.has(it.source));
  const q = state.query.trim();
  if (q) items = items.filter((it) => matchesNewsItem(it, q));
  return items;
}
