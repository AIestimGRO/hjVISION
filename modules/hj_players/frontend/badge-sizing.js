/* HJ PLAYERS v0.3.9 — module-local proportional name / symbol sizing.
 * Loaded after CORE common.js in both editor and OBS overlay.
 * The saved font_size remains a base-size preference, never a fixed visual size.
 */
'use strict';
(() => {
  if (typeof HJ === 'undefined') return;
  const originalPosition = HJ.positionBadge;
  HJ.fitBadge = function fitBadgeProportionally(el) {
    const canvas = el.parentElement;
    if (!canvas || !canvas.clientWidth || !canvas.clientHeight) return;
    const p = el._placement || {};
    const width = Math.max(.04, Number(p.width) || .15);
    const height = Math.max(.02, Number(p.height) || .065);
    const canvasScale = canvas.clientWidth / 1920;
    // Geometric scaling responds to BOTH width and height. The physical badge height
    // caps the text so it cannot protrude through the frame when resizing only width.
    const sizeFactor = Math.sqrt((width / .15) * (height / .065));
    const baseFont = Math.max(8, Number(p.font_size) || 24);
    const font = Math.max(3, Math.min(baseFont * canvasScale * sizeFactor,
                                  height * canvas.clientHeight * .65));
    el.style.setProperty('--canvas-scale', String(canvasScale));
    el.style.setProperty('--font-px', `${font}px`);
    const name = el.querySelector('.hj-name');
    if (!name) return;
    name.style.fontSize = `${font}px`;
    // Long nicknames are fitted into the available width (not ellipsized prematurely).
    if (name.clientWidth <= 0) return;
    for (let i = 0; i < 16 && name.scrollWidth > name.clientWidth + 1; i++) {
      const next = Math.max(3, parseFloat(name.style.fontSize) * .9);
      name.style.fontSize = `${next}px`;
      if (next <= 3) break;
    }
  };
  HJ.positionBadge = (el, p) => {
    originalPosition(el, p);
    HJ.fitBadge(el);
  };
})();
