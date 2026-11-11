# HJ TIMER OVERLAY 0.1.0 (test)

Standalone movable OBS timer/blind overlay for HI, JACK LIVE CORE API 1.x.

Source timer: `https://timer.hijackpoker.ru/api/state` (READ ONLY).

Install `hj_timer_overlay/` ZIP through Modules / Updates (after disconnecting OBS overlays), restart the application, then open `http://127.0.0.1:8765/timer-control`.

Add third OBS Browser Source: `http://127.0.0.1:8765/overlay/timer?layout=top`, set to 1920 x 1080 and fit to the 1920 x 1080 OBS canvas. Transparent background.

Supports top, side, extra camera profiles. For each, drag in 16:9 editor, choose width, style and visibility, click **Publish to OBS**. The preview screenshot is only stored locally in browser localStorage and is not broadcast. API never writes to the live TV timer.

On timer connection loss, OBS displays a small no-connection placeholder rather than continuing to count stale seconds. Changes to the server or the timer site are unnecessary.

### v0.2.0
Управление визуальной плашкой таймера перенесено в главную панель `/admin` при установленном HJ PLAYERS v0.3.8. Страница `/timer-control` осталась для совместимости. Данные с удалённого сайта читаются без изменения.
