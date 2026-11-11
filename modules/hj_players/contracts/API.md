# Public API — HJ Players

`players.api`: `get_active_players()`, `get_player(player_id)`. HTTP `/api/players`, `/api/profiles`, `/api/themes`.


## HJ PLAYERS v0.3.6 additions (backward compatible)
- `POST /api/profiles/{profile_id}/auto-place`: for the requested camera profile, updates only the saved DRAFT x/y values of players with seats to the default physical-box positions. Keeps rotation, size and appearance. Does NOT publish live changes.
- Existing `PUT /api/profiles/{profile_id}/draft` and `POST /api/profiles/{profile_id}/publish` remain unchanged.
- First-time assignment of `seat` through `PATCH /api/players/{pid}` automatically positions untouched center coordinates in every profile, preserving manually positioned layouts.
