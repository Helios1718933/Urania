/* ============================================================
   views/draw.js —— 抽取视图（含「回忆门」：模糊遮挡 + 倒计时 + 揭晓自评）
   ============================================================ */

import {
  $main, RECALL_SECONDS, api, esc, fmtClock, masteryLabel, refreshChip, state, toast,
} from "../core.js";
import { emptyBox, structuredBlock, tagsBlock, vizBlock } from "../components.js";
import { icons } from "../icons.js";

let recallTimerId = null;
let recallLeft = 0;

export function clearRecallTimer() {
  if (recallTimerId) {
    clearInterval(recallTimerId);
    recallTimerId = null;
  }
}

function startRecallTimer() {
  clearRecallTimer();
  recallLeft = RECALL_SECONDS;
  const label = document.getElementById("veil-timer-text");
  const chip = document.getElementById("veil-timer");
  if (!label || !chip) return;
  label.textContent = fmtClock(recallLeft);
  recallTimerId = setInterval(() => {
    recallLeft -= 1;
    const t = document.getElementById("veil-timer-text");
    const c = document.getElementById("veil-timer");
    if (t) t.textContent = fmtClock(Math.max(0, recallLeft));
    if (c) c.classList.toggle("warn", recallLeft <= 10);
    if (recallLeft <= 0) revealDraw();
  }, 1000);
}

/** 揭晓：内容模糊平滑退去，展示全部信息与三档自评（不知道→1 / 有点模糊→2 / 知道了→3） */
export function revealDraw() {
  clearRecallTimer();
  if (state.phase !== "recall" || !state.drawPoint) return;
  state.phase = "revealed";
  const p = state.drawPoint;

  const zone = document.getElementById("recall-zone");
  if (zone) {
    zone.classList.remove("is-blurred");       // filter 过渡：模糊 → 清晰
    zone.style.transition = "filter 0.55s ease";
  }
  const floats = document.getElementById("recall-float");
  if (floats) {
    floats.classList.add("float-leave");        // 提示浮层淡出
    setTimeout(() => floats.remove(), 260);
  }

  const actions = document.getElementById("draw-actions");
  if (!actions) return;
  actions.innerHTML = `
    <p class="recall-q">揭晓！诚实自评 —— 这个知识点你现在：</p>
    <div class="recall-row">
      <button class="recall-btn lv1" data-mastery="1"><strong>不知道</strong><span>初识 · 听说过</span></button>
      <button class="recall-btn lv2" data-mastery="2"><strong>有点模糊</strong><span>理解 · 能复述</span></button>
      <button class="recall-btn lv3" data-mastery="3"><strong>知道了</strong><span>熟悉 · 能解释</span></button>
    </div>
    <div class="recall-sub">
      <button class="btn btn-secondary" id="btn-redraw">换一个</button>
      <span class="kbd-hint"><kbd>R</kbd> 换一个</span>
    </div>`;

  actions.querySelectorAll(".recall-btn").forEach((opt) => {
    opt.addEventListener("click", async () => {
      const mastery = Number(opt.dataset.mastery);
      try {
        await api(`/api/points/${p.id}/learn`, {
          method: "POST",
          body: JSON.stringify({ mastery }),
        });
        toast(`已记录：${p.name} → ${masteryLabel(mastery).split(" · ")[0]}`);
        renderDraw();
        refreshChip();
      } catch (e) {
        toast(e.message);
      }
    });
  });
  document.getElementById("btn-redraw").addEventListener("click", renderDraw);
}

export async function renderDraw() {
  $main.innerHTML = `<p class="loading">正在抽取…</p>`;
  let data;
  try {
    data = await api("/api/draw");
  } catch (e) {
    $main.innerHTML = emptyBox("alert", "加载失败", e.message);
    return;
  }
  state.drawPoint = data.point;
  state.remaining = data.remaining;

  if (!data.point) {
    $main.innerHTML = `
      <section class="view">
        ${emptyBox("check", "全部知识点都已进入学习循环",
          "没有可抽取的未学习知识点了，去复习巩固一下吧。",
          `<button class="btn btn-primary" data-goto="review">去复习</button>`)}
      </section>`;
    return;
  }

  const p = data.point;
  state.phase = "recall";
  clearRecallTimer();
  $main.innerHTML = `
    <section class="view">
      <p class="view-caption">随机抽取一个未学习的知识点 · 还剩 ${data.remaining} 个未学习</p>
      <article class="card draw-card">
        <div><span class="pill pill-blue">${esc(p.category)}</span></div>
        <h2 class="draw-name">${esc(p.name)}</h2>
        <div class="recall-wrap">
          <div class="recall-zone is-blurred" id="recall-zone">
            ${structuredBlock(p)}
            ${vizBlock(p)}
            ${tagsBlock(p)}
          </div>
          <div class="recall-float" id="recall-float">
            <span class="veil-timer" id="veil-timer">${icons.clock}<span id="veil-timer-text">${fmtClock(RECALL_SECONDS)}</span></span>
            <div class="veil-center">
              <p class="veil-hint">先回忆一下</p>
              <p class="veil-sub">这个知识点讲的是什么？试着先自己说一遍</p>
            </div>
            <button type="button" class="veil-skip" id="btn-skip">跳过 · 立即揭晓</button>
          </div>
        </div>
        <div class="divider"></div>
        <div class="draw-actions" id="draw-actions">
          <button class="btn btn-secondary" id="btn-redraw">换一个</button>
          <span class="kbd-hint">空格 揭晓 · <kbd>R</kbd> 换一个</span>
        </div>
      </article>
    </section>`;

  document.getElementById("btn-redraw").addEventListener("click", renderDraw);
  document.getElementById("btn-skip").addEventListener("click", revealDraw);
  startRecallTimer();
}
