import { state } from "./state.js";
import { el } from "./utils.js";
import { filteredNewsItems } from "./search.js";

function getSourceCategoryMap() {
  const map = new Map();
  if (!state.news || !Array.isArray(state.news.items)) return map;
  // 出現順を維持(news.json は日付降順だが、ソース別の最初の出現順でチップ表示)
  for (const it of state.news.items) {
    if (it.source && it.category && !map.has(it.source)) {
      map.set(it.source, it.category);
    }
  }
  return map;
}

function renderNewsCard(item) {
  return el(
    "a",
    {
      class: "news-card",
      href: item.url,
      target: "_blank",
      rel: "noopener",
      "data-source": item.source || "",
    },
    [
      el("div", { class: "news-meta-row" }, [
        el(
          "time",
          { class: "news-date", datetime: item.date },
          item.date,
        ),
        el("span", { class: "news-category" }, item.category || ""),
      ]),
      el("h3", { class: "news-title" }, item.title || "(無題)"),
      item.summary
        ? el("p", { class: "news-summary" }, item.summary)
        : null,
    ],
  );
}

export function renderNewsView(root) {
  root.innerHTML = "";
  const news = state.news;
  if (!news || !Array.isArray(news.items)) {
    root.appendChild(
      el(
        "p",
        { class: "empty-message" },
        "新着情報を読み込めませんでした。",
      ),
    );
    return;
  }

  // カテゴリフィルタチップ
  const sourceCategoryMap = getSourceCategoryMap();
  if (sourceCategoryMap.size > 0) {
    const chips = [];
    for (const [source, category] of sourceCategoryMap) {
      const isActive = state.activeSources.has(source);
      const chip = el(
        "button",
        {
          class: `news-filter-chip${isActive ? " is-active" : ""}`,
          "data-source": source,
          type: "button",
          "aria-pressed": isActive ? "true" : "false",
        },
        category,
      );
      chip.addEventListener("click", () => {
        if (state.activeSources.has(source)) {
          state.activeSources.delete(source);
        } else {
          state.activeSources.add(source);
        }
        // 循環インポート回避: 再描画は CustomEvent で main.js に依頼
        document.dispatchEvent(new CustomEvent("news:filter-changed"));
      });
      chips.push(chip);
    }
    root.appendChild(el("div", { class: "news-filters" }, chips));
  }

  const filtered = filteredNewsItems();
  if (filtered.length === 0) {
    const isFiltering =
      state.query.trim() !== "" ||
      state.activeSources.size < sourceCategoryMap.size;
    root.appendChild(
      el(
        "p",
        { class: "empty-message" },
        isFiltering
          ? "条件に一致する新着情報はありません。"
          : "新着情報はありません。",
      ),
    );
    return;
  }
  root.appendChild(
    el("div", { class: "news-list" }, filtered.map(renderNewsCard)),
  );
}
