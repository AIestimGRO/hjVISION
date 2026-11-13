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

/* HJ PLAYERS avatar mode — same rendering in editor and OBS. */
(() => {
  if (typeof HJ === 'undefined') return;
  const makeOriginal = HJ.makeBadge;
  HJ.makeBadge = function(player, placement, selected, settings) {
    const badge = makeOriginal(player, placement, selected, settings);
    const mode = player.display_mode || 'nickname';
    if (mode === 'nickname' || !player.avatar_revision) return badge;
    badge.classList.add('hj-has-avatar');
    badge.classList.add(mode === 'avatar' ? 'hj-avatar-only' : 'hj-avatar-with-name');
    const inner = badge.querySelector('.hj-inner');
    if (inner) {
      const picture = document.createElement('img');
      picture.className = 'hj-player-avatar';
      picture.alt = '';
      picture.draggable = false;
      picture.src = '/api/players/' + encodeURIComponent(player.id) +
                    '/avatar?v=' + encodeURIComponent(player.avatar_revision);
      picture.onerror = () => { badge.classList.remove('hj-avatar-only','hj-avatar-with-name','hj-has-avatar'); picture.remove(); };
      inner.prepend(picture);
      inner.querySelector('.hj-gem')?.remove();
    }
    return badge;
  };
})();
