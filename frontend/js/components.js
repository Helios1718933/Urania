/* ============================================================
   components.js —— 可复用的 HTML 片段（纯函数，无副作用）
   依赖 core 的转义与领域格式化；被各视图引用。
   ============================================================ */

import { esc, fmtDate, masteryLabel } from "./core.js";
import { icons } from "./icons.js";

/** 掌握度圆点（5 档，4 档以上变绿） */
export function masteryDots(m) {
  const dots = [1, 2, 3, 4, 5]
    .map((i) => `<i class="${i <= m ? "on" : ""}"></i>`).join("");
  return `<span class="mastery-dots ${m >= 4 ? "m4" : ""}" title="${esc(masteryLabel(m))}">${dots}</span>`;
}

/** 列表右侧的状态徽章（到期 / 已掌握 / 排期） */
export function statusBadge(point) {
  if (point.is_due) return `<span class="badge badge-due">今天该复习</span>`;
  if (point.status === "mastered") return `<span class="badge badge-mastered">已掌握</span>`;
  return `<span class="badge badge-scheduled">${fmtDate(point.next_review_at)}</span>`;
}

/** 可视化区：http(s) 链接渲染成外链，否则当文字说明 */
export function vizBlock(point) {
  const v = String(point.visualization || "").trim();
  if (!v) return "";
  if (/^https?:\/\//i.test(v)) {
    return `<div class="viz"><a class="viz-link" href="${esc(v)}" target="_blank" rel="noopener">`
      + `查看可视化讲解 ${icons.external}</a></div>`;
  }
  return `<div class="viz"><span class="viz-note">可视化 · ${esc(v)}</span></div>`;
}

export function tagsBlock(point) {
  if (!point.tags?.length) return "";
  return `<div class="tags">${point.tags.map((t) => `<span class="tag"># ${esc(t)}</span>`).join("")}</div>`;
}

export function principleBlock(point) {
  return `<div class="draw-principle">${esc(point.principle || "（暂无原理讲解）")}</div>`;
}

/**
 * 空状态卡片。
 * @param {keyof typeof icons} icon  图标名（见 icons.js，替代 emoji）
 * 注意：title/desc 会转义；actionHTML 是前端自己写的受控片段，直接透传。
 */
export function emptyBox(icon, title, desc, actionHTML = "") {
  return `
    <div class="empty">
      <div class="empty-icon">${icons[icon] ?? ""}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(desc)}</p>
      ${actionHTML}
    </div>`;
}
