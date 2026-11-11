## 0.3.10 — Preset standard pлашки
- Advanced settings: Save as standard saves the selected badge visual settings to SQLite.
- New players use the saved standard in every camera profile; dealer excluded.
- Apply to all in current profile changes only draft appearance, never screen coordinates or visibility.
- Restore standard uses the saved standard, not hardcoded defaults.
- Existing layouts and on-air OBS overlays stay unchanged until explicitly published.

# HJ PLAYERS v0.3.9 — 2026-11-11 (test / operator verification required)

- «Обычная» / «Расширенная» настройка выбранной плашки; по умолчанию простая настройка.
- Панель выбранной плашки перенесена сразу под 16:9 редактор, выше галереи тем.
- В обычном режиме только три направления поворота. Размер меняется мышью за угол с сохранением пропорций.
- Размер текста и символа растёт/уменьшается вместе с плашкой в редакторе И OBS. Для длинных имён работает вписывание по ширине; высота ограничивает шрифт.
- Расширенный режим сохраняет все старые ползунки, включая базовый размер шрифта; выбор режима хранится только локально в браузере.
- Вне модуля ничего не меняется: CORE, API, таймер, координаты, публикуемый черновик, настройки игроков и SQLite прежние.

# HJ PLAYERS v0.3.8 — 2026-11-11

- Встроенная панель HJ TIMER OVERLAY в основном окне (если установлен модуль таймера v0.2+).
- Общий 16:9 предпросмотр таймера с никнеймами, перетаскивание без отдельной вкладки.
- Размеры 1920×1080 относятся к OBS-кадру; сам редактор автоматически вписывается в окно.
- Сохранена логика рассадки, игроков и опубликованных профилей v0.3.7.

Для работы панели установите HJ TIMER OVERLAY v0.2.0. Нет изменения схемы данных HJ PLAYERS.
## 0.3.7 — Camera frame parity / 16:9 precision editor (trial)
- Confirmed native 16:9 preview (1920x1080 coordinate system) and introduced a full-width editor to make placing badges on real top-view video much easier; it automatically expands in editor mode, and can be toggled without changing on-air positions.
- Added explicit 16:9/1920x1080 frame labeling and guidance to use an uncropped full OBS scene image as the reference, not a cropped photo.
- Reference camera image upload now fits inside 1920x1080 with black letterboxing rather than cropping the image. Non-16:9 image inputs trigger a visible warning with the source dimensions; this avoids misleading seat mapping.
- Backdrop remains local preview only, never sent to OBS; no change to API, CORE, state schema, stored placements or video output.
- Keeps all HJ PLAYERS 0.3.6 fixes including auto-seat, manual drag, 90-degree rotation, and draft/publish separation.

## 0.3.6 — HJ PLAYERS (trial / requires Windows 11 operator approval)
- First assignment of a physical box automatically positions previously unseated players in each camera profile, without overwriting manually changed positions.
- Explicit «Расставить по боксам» creates a draft with default positions for already seated legacy players; published OBS coordinates stay untouched until approval.
- Quick 90° counter-clockwise, horizontal 0°, and 90° clockwise rotation controls for side-box badges. Existing rotation slider stays available.
- Moved the publish controls above the themes section and added an always-visible-in-editor «Опубликовать в OBS» button near mode selection.
- Fix draft save and publish ordering: await pending writes; show save errors; verify server acknowledged published coordinates; prompt to publish when leaving editor with an unpublished draft.
- Added regression coverage for seat auto-positioning, customized layouts, rotation, draft/published separation, OBS WebSocket and restart persistence.
- No CORE contract or other module changes. Same versioned state-v2 JSON and SQLite schema.

## 0.3.2
- Fixed missing migrations directory in module package.
- Removed modal background GPU blur for WebView2 stability.
- Added guarded player form submission and deferred input focus.

## 0.3.1
- Native desktop mode: visible close/exit button in the player control page; HTTP/browser mode remains compatible.

# Изменения

- 0.3.0: Перенос из приложения v0.2 без изменения совместимых маршрутов.
