# Vercel + Supabase Web Deploy Plan

## Goal

Use Supabase as PostgreSQL and deploy the existing pixel frontend plus FastAPI backend to one Vercel project.

## Implementation

- Add `api/index.py` as the Vercel Python entrypoint that imports the existing `main.app`.
- Add `vercel.json` so `/api/*` and `/health` are handled by FastAPI while static files are served from `frontend/`.
- Update `frontend/api.js` so local hosts still call port `8000`, while production hosts use same-origin API calls.
- Add `.vercelignore` to keep local virtual environments, logs, backups, and generated output out of deployments.
- Add `deploy/README-vercel.md` with the exact user-facing setup flow and environment variables.

## Verification

- `node --test tests\vercel-deploy.test.js`
- `node --test tests\*.test.js`
- `python -m pytest`
