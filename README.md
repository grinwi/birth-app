# Birthdays App (Next.js + Python) — Blob JSON as runtime DB with GitHub JSON backup

The app uses Vercel Blob to store the dataset as a single JSON document (e.g., `birthdays.json`). The UI edits write to Blob immediately, and each change opens a GitHub Pull Request that updates a JSON snapshot in your repository. This provides a simple, auditable, versioned backup while keeping the live data in Blob.

No KV fallback is used at runtime.

## Architecture

- Runtime source of truth: Vercel Blob JSON (one document, e.g., `birthdays.json`).
- Backup and audit: GitHub JSON snapshot committed via PR on every mutation.
- Bootstrap/Recovery: A protected sync endpoint loads the JSON from GitHub into Blob (one-shot during deployment or for recovery).

## Endpoints (Python)

All endpoints are authenticated with cookie-based, HttpOnly JWT. Admin-specific routes require an admin role.

- `GET /api-py/people`
  - Returns the current rows from Blob.
- `POST /api-py/people`
  - Adds a person. Writes to Blob and opens a GitHub PR updating the JSON snapshot.
- `PUT /api-py/people?index=N`
  - Updates a person at index N. Writes to Blob and opens a GitHub PR updating JSON.
- `DELETE /api-py/people?index=N`
  - Deletes a person at index N. Writes to Blob and opens a GitHub PR updating JSON.

- `GET /api-py/json`
  - Returns the entire dataset from Blob (`{ data: [...] }`).
- `POST /api-py/json` (admin)
  - Accepts either an array of rows or `{ "data": [...] }`.
  - Writes to Blob and opens a JSON-only PR to GitHub.

- `GET /api-py/sync` (protected)
  - Dry-run: Loads JSON from GitHub and reports row count (no write).
- `POST /api-py/sync` (protected)
  - Performs the sync: loads JSON from GitHub and writes it to Blob. Use during deployment bootstrap or recovery.
  - Protection: Provide `BOOTSTRAP_TOKEN` via `Authorization: Bearer`, `X-Bootstrap-Token`, or `?token=`.

Auth endpoints:
- `POST /api-py/auth/login`
- `POST /api-py/auth/invite` (admin)
- `POST /api-py/auth/register`

## Environment Variables

Set these in Vercel (Project Settings → Environment Variables) for Production and Preview. For local `vercel dev`, mirror them in `.env.local`.

Required (Blob runtime DB)
- `BLOB_BASE_URL` — Public base URL of your Blob store  
  Example: `https://<bucket-id>.public.blob.vercel-storage.com`
- `BLOB_READ_WRITE_TOKEN` — Read/Write token from Blob (Settings → Tokens)
- `BLOB_JSON_KEY` — Object key/filename for the JSON document (e.g., `birthdays.json`)

Required (GitHub JSON backup via PR)
- `GITHUB_TOKEN` — Fine-grained PAT with repository access to the target repo, minimum:
  - Contents: Read/Write
  - Pull requests: Read/Write
- `GITHUB_REPO_OWNER` — e.g., `grinwi`
- `GITHUB_REPO` — e.g., `birth-app`
- `GITHUB_BRANCH` — e.g., `main`
- `GITHUB_JSON_FILE_PATH` — e.g., `birthdays.json` (the snapshot committed in PRs)

Required for Auth/Admin
- `AUTH_SECRET` — Long random secret for signing JWTs (HS256)
- `ADMIN_INITIAL_PASSWORD` — One-time password for `admin` to bootstrap the first admin

Optional
- `AUTH_TOKEN_TTL_SECONDS` — JWT max age in seconds (default 1209600 = 14 days)
- `BOOTSTRAP_TOKEN` — Required to authorize `/api-py/sync` (bootstrap/recovery)

## Bootstrap / Recovery

After deploying, initialize Blob from the GitHub JSON snapshot:

- Dry-run:
  ```
  GET https://your-deployment.vercel.app/api-py/sync?token=YOUR_BOOTSTRAP_TOKEN
  ```
- Perform sync:
  ```
  POST https://your-deployment.vercel.app/api-py/sync
  Authorization: Bearer YOUR_BOOTSTRAP_TOKEN
  ```

The app then reads only from Blob. Every UI change updates Blob and opens a GitHub PR updating `GITHUB_JSON_FILE_PATH`.

## Local Development

Option A: Full stack with Vercel dev
- Install and login:
  ```
  npm i -g vercel
  vercel login
  ```
- Copy `.env.example` to `.env.local` and fill values.
- Run:
  ```
  vercel dev
  ```
- Visit http://localhost:3000
- First-time admin bootstrap:
  - Go to `/login` and sign in as username `admin` with `ADMIN_INITIAL_PASSWORD`.

Option B: Next-only
- `npm run dev`
- Python routes under `/api-py/*` will not be served in Next-only dev; use `vercel dev` to exercise backend endpoints locally.

## Data Format

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
The JSON stored in Blob is an array of such rows.

## Security

- Keep secrets (`BLOB_READ_WRITE_TOKEN`, `GITHUB_TOKEN`, `AUTH_SECRET`) server-side; never expose to client code.
- Use a strong `BOOTSTRAP_TOKEN`; rotate regularly if you use the sync endpoint.

## Notes

- KV is not used at runtime.
- The JSON snapshot in GitHub acts as a durable, auditable backup while Blob holds the live data.
