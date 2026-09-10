/* ============================================================
   views/review.js —— 复习列表与知识点详情（自评三档）
   ============================================================ */

import { $main, api, esc, fmtDate, masteryLabel, refreshChip, toast } from "../core.js";
import {
  emptyBox, masteryDots, principleBlock, statusBadge, tagsBlock, vizBlock,
} from "../components.js";

export async function renderReviewList() {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let data;
  try {
    data = await api("/api/review/queue");
  } catch (e) {
    $main.innerHTML = emptyBox("alert", "加载失败", e.message);
    return;
  }

  if (!data.items.length) {
    $main.innerHTML = `
      <section class="view">
        ${emptyBox("tray", "还没有已学习的知识点", "先去抽取一个新知识点，标记学习后就会出现在这里。",
          `<button class="btn btn-primary" data-goto="draw">去抽取新知识</button>`)}
      </section>`;
    return;
  }

  const dueCount = data.items.filter((x) => x.is_due).length;
  const rows = data.items.map((p) => `
    <div class="list-row" data-id="${p.id}" role="button" tabindex="0">
      <div class="row-main">
        <div class="row-name">${esc(p.name)}</div>
        <div class="row-sub">${esc(p.category)} · 已复习 ${p.review_count} 次</div>
      </div>
      <div class="row-side">
        ${masteryDots(p.mastery)}
        ${statusBadge(p)}
      </div>
      <span class="chevron">›</span>
    </div>`).join("");

  $main.innerHTML = `
    <section class="view">
      <p class="view-caption">已学习的知识点 · 共 ${data.items.length} 个${dueCount ? `，其中 ${dueCount} 个今天该复习` : ""}</p>
      <div class="list-group">${rows}</div>
    </section>`;

  document.querySelectorAll(".list-row").forEach((row) => {
    const open = () => renderReviewDetail(Number(row.dataset.id));
    row.addEventListener("click", open);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });
}

export async function renderReviewDetail(pointId) {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let point;
  try {
    point = (await api(`/api/points/${pointId}`)).point;
  } catch (e) {
    $main.innerHTML = emptyBox("alert", "加载失败", e.message);
    return;
  }

  $main.innerHTML = `
    <section class="view">
      <button class="back-btn" id="btn-back">‹ 返回复习列表</button>
      <article class="card draw-card">
        <div class="detail-meta">
          <span class="pill pill-blue">${esc(point.category)}</span>
          ${point.status === "mastered" ? `<span class="badge badge-mastered">已掌握</span>` : ""}
        </div>
        <h2 class="draw-name">${esc(point.name)}</h2>
        <p class="detail-mastery">
          ${masteryDots(point.mastery)}&nbsp;&nbsp;${esc(masteryLabel(point.mastery))}
          · 已复习 ${point.review_count} 次 · 上次复习 ${fmtDate(point.last_reviewed_at)}
        </p>
        <div class="divider"></div>
        ${principleBlock(point)}
        ${vizBlock(point)}
        ${tagsBlock(point)}
        <div class="divider"></div>
        <div class="rating-group">
          <p>凭记忆回想一遍，诚实自评：</p>
          <div class="rating-row">
            <button class="btn btn-rate-forgot" data-rating="forgot">忘了</button>
            <button class="btn btn-rate-fuzzy" data-rating="fuzzy">有点模糊</button>
            <button class="btn btn-rate-solid" data-rating="solid">记住了</button>
          </div>
        </div>
        <div class="danger-zone">
          <button class="btn-text-danger" id="btn-reset">重置为未学习</button>
        </div>
      </article>
    </section>`;

  document.getElementById("btn-back").addEventListener("click", renderReviewList);
  document.querySelectorAll(".rating-row .btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const rating = btn.dataset.rating;
      try {
        const r = await api(`/api/points/${point.id}/review`, {
          method: "POST",
          body: JSON.stringify({ rating }),
        });
        toast(`${r.point.name} · ${masteryLabel(r.point.mastery)}，下次 ${fmtDate(r.point.next_review_at)}`);
        renderReviewDetail(point.id);
        refreshChip();
      } catch (e) {
        toast(e.message);
      }
    });
  });
  document.getElementById("btn-reset").addEventListener("click", async () => {
    if (!window.confirm(`确定把「${point.name}」重置为未学习吗？学习记录将被清除（复习历史会保留）。`)) return;
    try {
      await api(`/api/points/${point.id}/record`, { method: "DELETE" });
      toast("已重置为未学习");
      renderReviewList();
      refreshChip();
    } catch (e) {
      toast(e.message);
    }
  });
}
