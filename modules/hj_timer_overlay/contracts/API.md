# Local API 1.0
- GET /api/hj-timer/state: {connected:boolean,state:null|{status,kind,remaining_sec,level,label,sb,bb,ante,server_time}}
- GET /api/hj-timer/layout?profile=top|side|extra: {profile,layout} (published only)
- GET /api/hj-timer/config: {published,drafts,revision} (admin token)
- PUT /api/hj-timer/draft/{profile}: LayoutInput (admin token)
- POST /api/hj-timer/publish/{profile}: same config (admin token)
- POST /api/hj-timer/discard/{profile}: same config (admin token)
- UI /timer-control; OBS /overlay/timer?layout=top|side|extra
