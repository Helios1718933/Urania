/* ============================================================
   icons.js —— 内联 SVG 图标（替代 emoji）
   规范依据：ui-ux-pro-max 把「Emoji as icons」列为反模式；
   这里用 currentColor 描边的极简几何图标，随文字颜色与深浅色自适应。
   尺寸由 CSS 的 .empty-icon svg / .icon 控制。
   ============================================================ */

const wrap = (path, extra = "") => `<svg viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.7" stroke-linecap="round"
  stroke-linejoin="round" aria-hidden="true" focusable="false">${path}${extra}</svg>`;

export const icons = {
  /** 完成 / 已就绪 */
  check: wrap(`<path d="M20 6.5 9.2 17.3 4 12.1"/>`),

  /** 空托盘（没有已学习的知识点） */
  tray: wrap(`<path d="M3.5 13h4l1.5 3h6l1.5-3h4"/>
    <path d="M6 4.5h12l2.2 8.2v5.3a1.5 1.5 0 0 1-1.5 1.5H5.3a1.5 1.5 0 0 1-1.5-1.5v-5.3z"/>`),

  /** 警告（加载失败） */
  alert: wrap(`<circle cx="12" cy="12" r="8.5"/><path d="M12 7.8v5"/>`,
    `<circle cx="12" cy="16.2" r="1" fill="currentColor" stroke="none"/>`),

  /** 计时（回忆门倒计时） */
  clock: wrap(`<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/>`),

  /** 外链（可视化链接） */
  external: wrap(`<path d="M14 4.5h5.5V10"/><path d="M19.5 4.5 11 13"/>
    <path d="M18 14.5v4a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6h4"/>`),
};

/** 包一层统一样式的容器（空状态大图标用） */
export function iconBox(name, size = 30) {
  const svg = icons[name] ?? "";
  return `<span class="icon" style="width:${size}px;height:${size}px">${svg}</span>`;
}
