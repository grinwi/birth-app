# Birthdays App (Next.js + Python) — Storage: Vercel Blob (JSON) with GitHub CSV PRs

This app uses Vercel Blob as the primary datastore, storing the full dataset as a single JSON document (e.g., `birthdays.json`). On each mutation, the backend also generates a CSV from the JSON and opens a GitHub Pull Request for audit/versioning. There is no file-based persistence on the server — Vercel Blob is the “db file”.

KV remains as a fallback (optional) if Blob is not configured yet.

## Why CSV still appears

CSV exists only as a PR-managed artifact. The live data is in Blob (`birthdays.json`). When a change happens (add/update/delete), the backend:
1) Writes the updated rows to Blob (JSON).
2) Generates both `birthdays.json` (pretty, canonical backup) and `birthdays.csv` (tabular) from those rows and opens a PR against your GitHub repo for review/history.

## Backend endpoints (Python)

- `GET  /api-py/people` — returns JSON rows (Blob-first, KV fallback)
- `POST /api-py/people` — add person (auth required), writes to Blob, opens PR for CSV
- `PUT  /api-py/people?index=N` — update person at index (auth required), writes to Blob, opens PR
- `DELETE /api-py/people?index=N` — delete person at index (auth required), writes to Blob, opens PR
- `GET  /api-py/csv` — returns CSV derived from Blob
- `POST /api-py/csv` — accepts CSV or JSON rows to replace the dataset (admin only), writes Blob + opens PR

Auth endpoints (cookie-based, HttpOnly JWT):
- `POST /api-py/auth/login`
- `POST /api-py/auth/invite` (admin)
- `POST /api-py/auth/register`

## Environment Variables

Configure these in Vercel (Project Settings → Environment Variables). Add to Production, Preview, and Development as needed. For local `vercel dev`, copy them into a `.env.local`.

Required for Blob (primary datastore)
- BLOB_BASE_URL
  - The public base URL of your Blob store.
  - Example: `https://<bucket-id>.public.blob.vercel-storage.com`
- BLOB_READ_WRITE_TOKEN
  - A Read/Write token from your Blob store (create under “Settings → Tokens”).
- BLOB_JSON_KEY (optional, default: `birthdays.json`)
  - The object key (path/filename) for the JSON document.

Required for GitHub PRs (CSV mirror)
- GITHUB_TOKEN
  - GitHub Personal Access Token (classic or fine-grained) with `contents:write` on the repo.
- GITHUB_REPO_OWNER
  - Example: `grinwi`
- GITHUB_REPO
  - Example: `birth-app`
- GITHUB_BRANCH
  - Example: `main`
- GITHUB_FILE_PATH
  - Example: `birthdays.csv`
- GITHUB_JSON_FILE_PATH
  - Example: `birthdays.json` (JSON snapshot committed alongside CSV)

Required for Auth / Admin bootstrap
- AUTH_SECRET
  - Long random secret for signing JWTs (HS256). 64+ characters recommended.
- ADMIN_INITIAL_PASSWORD
  - One-time bootstrap password. Sign in as username `admin` once to create the first admin user.

Optional (fallback KV; only needed if you want KV as a fallback)
- KV_REST_API_URL
- KV_REST_API_TOKEN

Optional
- AUTH_TOKEN_TTL_SECONDS
  - JWT max age in seconds (default: 1209600 = 14 days).

## How to obtain Vercel Blob credentials

1) Open your Vercel dashboard → Storage → “Blob” → Create a Blob store (pick region).
2) In the Blob store page:
   - Copy the **Public Base URL** → set as `BLOB_BASE_URL`.
   - Create a **Read/Write Token** under “Settings → Tokens” → set as `BLOB_READ_WRITE_TOKEN`.
3) Optionally set `BLOB_JSON_KEY` if you want a custom filename/path (default is `birthdays.json`).
4) Add these to your Vercel project’s Env Vars. For local dev, mirror them in `.env.local`.

## Data flow and fallback

- On each mutation, the backend writes the updated rows to Vercel Blob (JSON) and opens a GitHub PR that commits BOTH:
  - JSON (path: `GITHUB_JSON_FILE_PATH`, pretty-printed) for canonical backup/restore
  - CSV (path: `GITHUB_FILE_PATH`) for audit/review and easy diff
- Read order at runtime:
  1) Blob (JSON)
  2) GitHub JSON (raw file in the repo)
  3) GitHub CSV (parsed)
  4) KV (if configured)
- This ensures GitHub acts as a durable backup/source of truth if Blob is missing or cleared; restoring is as simple as merging JSON in Git and redeploying.

## Local development

Option A (recommended): run full stack with Vercel
- Install and login:
  - `npm i -g vercel`
  - `vercel login`
- Create `.env.local` in project root with all variables above.
- Run:
  - `vercel dev`
- Visit http://localhost:3000
- First-time admin bootstrap:
  - Go to `/login` and sign in as `admin` using `ADMIN_INITIAL_PASSWORD`.

Option B (Next-only)
- `npm run dev`
- Note: Python routes under `/api-py/*` will NOT be served by Next-only dev. The UI will fall back to the read-only CSV from GitHub. Use `vercel dev` to test backend locally.

## Seeding / migrating data to Blob

Use `POST /api-py/csv`:

- CSV input (Content-Type: `text/csv`): body is the CSV file.
- JSON input (Content-Type: `application/json`): either an array of row objects or:
  ```json
  { "data": [ { "first_name":"Ada", "last_name":"Lovelace", "day":"10", "month":"12", "year":"1815" } ] }
  ```
This replaces the dataset in Blob and opens a PR updating `birthdays.csv`.

## Data format

Each person row is:
```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "day": "10",
  "month": "12",
  "year": "1815"
}
```
The JSON stored in Blob is a list of such rows.

## Notes

- Security: Keep all secrets (`BLOB_READ_WRITE_TOKEN`, `GITHUB_TOKEN`, `AUTH_SECRET`) out of the client; they are server-side only.
- CSV file in the repo is generated for audit/versioning via PRs. It is not used as a datastore.
- If Blob is not configured, the backend will attempt KV (if provided) as a fallback.
