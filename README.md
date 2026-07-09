# STRATZ Dota Analytics API

FastAPI MVP for Dota 2 player analytics, local ratings, hero stats, and achievements powered by STRATZ GraphQL.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d --build
```

Open API docs at <http://127.0.0.1:8000/docs>.

`STRATZ_TOKEN` must be a fresh token in `.env`. Do not reuse a token that has been pasted into chat or committed to a repository.

## Main Endpoints

- `GET /health`
- `POST /v1/players/{account_id}/refresh`
- `GET /v1/jobs/{job_id}`
- `GET /v1/players/{account_id}/summary`
- `GET /v1/players/{account_id}/breakdowns`
- `GET /v1/players/{account_id}/matches`
- `GET /v1/players/{account_id}/heroes`
- `GET /v1/players/{account_id}/achievements`
- `GET /v1/players/{account_id}/rating`
- `GET /v1/players/{account_id}/style?limit=20`
- `GET /v1/heroes/winrates`
- `GET /v1/heroes/{hero_id}/builds`
- `GET /v1/leaderboard`

Global STRATZ hero winrates:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/heroes/winrates?limit=20&min_matches=10000&order_by=winRate"
```

Meta hero builds from STRATZ item/talent statistics:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/heroes/84/builds?min_matches=1000&limit=10"
```

Style score compares the player's final item build with the popular meta composition and compares
the exact skill-level order with the meta choice for each level. Higher deviation means a higher
score; the first request enriches up to 100 recent matches and caches the STRATZ payloads.
```

Player match type breakdowns:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/players/175966938/breakdowns"
```

Player analytics endpoints accept `limit` up to `500`, for example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/players/175966938/summary?limit=100"
Invoke-RestMethod "http://127.0.0.1:8000/v1/players/175966938/breakdowns?limit=500"
Invoke-RestMethod "http://127.0.0.1:8000/v1/players/175966938/heroes?limit=500"
Invoke-RestMethod "http://127.0.0.1:8000/v1/players/175966938/rating?limit=250"
```

## Notes

The app stores raw STRATZ GraphQL responses first in `source_payloads`, then derives normalized match/player rows and analytics. If STRATZ omits an optional field, dependent achievements are marked unavailable instead of failing the refresh.

## STRATZ Cloudflare 403

If refresh fails with `STRATZ returned a Cloudflare challenge (HTTP 403)`, the request was blocked before GraphQL and the token/query were not evaluated. Confirm with:

```powershell
python scripts/diagnose_stratz.py
```

Legitimate fixes are:

- run the API from a clean server/VPS network that STRATZ accepts;
- use a permitted proxy/egress you control via `STRATZ_PROXY_URL`;
- contact STRATZ support with the `CF-RAY`/trace printed by the diagnostic script;
- avoid scraping/bypass libraries that defeat Cloudflare challenges.
