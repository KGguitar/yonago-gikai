// 共有状態。各モジュールが import { state } で参照する。
// ES Modules のインポート束縛はライブ参照のため、複数モジュール間で
// 同一オブジェクトを共有できる。
export const state = {
  members: [],
  meta: null,
  links: {},
  news: null,
  activeSources: new Set(),
  view: "kaiha",
  query: "",
};
