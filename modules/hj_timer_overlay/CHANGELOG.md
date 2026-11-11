# HJ TIMER OVERLAY 0.2.0 — 2026-11-11

- Управление внутри HI, JACK LIVE; отдельный /timer-control оставлен для совместимости, но не обязателен.
- Единый превью 16:9 со всеми никнеймами, перетаскивание таймера в режиме редактора.
- Новые варианты минималистичный и BRONZE PREMIUM, улучшенные векторные шрифты, бордюры и антивизуальный алиасинг в OBS.
- Черновик/публикация, размер, прозрачность и видимость для каждого ракурса.
- API турнирного таймера используется только для чтения; удалённое управление ходом турнира не изменяется.
- Данные v0.1.0 совместимы без миграции.
# v0.1.0 · 2026-11-11 · TEST

- NEW independent module: read-only connection to official Hi, Jack Club tournament timer via `/api/state`.
- Display current blinds, ante, round, countdown and break/paused states.
- Transparent 1920×1080 OBS Browser Source independent from players and effects.
- 16:9 drag-and-drop editor, adjustable width and transparency, optional level/ante, horizontal or narrow layout, visibility toggle.
- Distinct positions for top, side and extra cameras.
- Draft/publish flow, browser-only camera reference screenshot, persistent user settings, no server changes.
- Bounded HTTPS polling, redacted JSON bridge, safe fail-closed connection handling.
