import { state } from "./state.js";
import { el } from "./utils.js";
import { filteredMembers, filteredNewsItems } from "./search.js";
import {
  renderKaihaView,
  renderCommitteeView,
  renderRoleView,
  renderTermView,
} from "./render-members.js";
import { renderNewsView } from "./render-news.js";

function renderMeta() {
  const node = document.getElementById("meta");
  if (!node) return;
  if (state.view === "news") {
    const news = state.news;
    if (!news) {
      node.textContent = "新着情報を読み込めませんでした";
      return;
    }
    const fetched = news.updated_at
      ? new Date(news.updated_at).toLocaleString("ja-JP")
      : "?";
    const count = (news.items && news.items.length) || 0;
    node.textContent = `新着 ${count} 件 / 最終取得 ${fetched}`;
    return;
  }
  const meta = state.meta;
  const members = state.members;
  if (!meta) {
    node.textContent = `現在 ${members.length} 人を表示`;
    return;
  }
  const fetched = meta.fetched_at
    ? new Date(meta.fetched_at).toLocaleString("ja-JP")
    : "?";
  node.textContent = `現在 ${members.length} 人 / 最終取得 ${fetched}`;
}

function updateMatchCount(filteredCount) {
  const node = document.getElementById("match-count");
  if (!node) return;
  if (state.view === "news") {
    const total =
      state.news && Array.isArray(state.news.items)
        ? state.news.items.length
        : 0;
    if (filteredCount !== total) {
      node.textContent = `${total}件中 ${filteredCount}件を表示`;
    } else {
      node.textContent = "";
    }
    return;
  }
  const total = state.members.length;
  if (state.query.trim()) {
    node.textContent = `${total}人中 ${filteredCount}人を表示`;
  } else {
    node.textContent = "";
  }
}

function updateSearchPlaceholder() {
  const input = document.getElementById("search");
  if (!input) return;
  input.placeholder =
    state.view === "news"
      ? "タイトル / 概要 / カテゴリ で検索"
      : "氏名 / ふりがな / 会派 / 委員会 で検索";
}

function render() {
  const main = document.getElementById("main");
  document.body.classList.toggle("is-news-view", state.view === "news");
  updateSearchPlaceholder();
  renderMeta();

  if (state.view === "news") {
    const filteredNews = filteredNewsItems();
    updateMatchCount(filteredNews.length);
    renderNewsView(main);
    return;
  }

  const filtered = filteredMembers();
  updateMatchCount(filtered.length);

  if (state.query.trim() && filtered.length === 0) {
    main.innerHTML = "";
    main.appendChild(
      el("p", { class: "empty-message" }, "該当する議員はいません。"),
    );
    return;
  }

  if (state.view === "kaiha") renderKaihaView(main, filtered);
  else if (state.view === "committee") renderCommitteeView(main, filtered);
  else if (state.view === "role") renderRoleView(main, filtered);
  else if (state.view === "term") renderTermView(main, filtered);
}

function setupTabs() {
  const tabs = document.querySelectorAll(".view-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.view;
      if (!view || view === state.view) return;
      tabs.forEach((t) => t.classList.toggle("is-active", t === tab));
      state.view = view;
      render();
    });
  });
}

function setupSearch() {
  const input = document.getElementById("search");
  const clearBtn = document.getElementById("search-clear");
  if (!input) return;

  input.addEventListener("input", () => {
    state.query = input.value;
    if (clearBtn) clearBtn.hidden = state.query.length === 0;
    render();
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      state.query = "";
      clearBtn.hidden = true;
      input.focus();
      render();
    });
  }
}

async function load() {
  const status = document.getElementById("status");
  try {
    const [membersRes, metaRes, linksRes, newsRes] = await Promise.all([
      fetch("./data/members.json", { cache: "no-cache" }),
      fetch("./data/meta.json", { cache: "no-cache" }),
      fetch("./data/member_links.json", { cache: "no-cache" }),
      fetch("./data/news.json", { cache: "no-cache" }),
    ]);
    if (!membersRes.ok) throw new Error(`members.json: ${membersRes.status}`);
    state.members = await membersRes.json();
    state.meta = metaRes.ok ? await metaRes.json() : null;
    state.links = linksRes.ok ? await linksRes.json() : {};
    state.news = newsRes.ok ? await newsRes.json() : null;
    // 初期状態: 全ソースをアクティブに
    if (state.news && Array.isArray(state.news.items)) {
      state.activeSources = new Set(
        state.news.items
          .map((it) => it.source)
          .filter((s) => typeof s === "string" && s),
      );
    }
    render();
  } catch (err) {
    console.error(err);
    if (status) status.textContent = `読み込みに失敗しました: ${err.message}`;
  }
}

// 起動: type="module" は defer 同等で DOM 構築後に実行されるため、
// DOMContentLoaded を待たずに直接呼び出して問題なし。
// チップクリック等から発火される再描画要求を受け取る。
document.addEventListener("news:filter-changed", () => render());
setupTabs();
setupSearch();
load();
