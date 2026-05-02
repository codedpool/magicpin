# Render deployment runbook — Vera Bot

Goal: get the bot live on a public HTTPS URL so the magicpin judge harness can call its 5 endpoints.

## Prerequisites

- GitHub account
- Render account (sign up at https://render.com — free, no card)
- Supabase project already running (Phase 0)
- `.env` populated locally with real credentials (gitignored — won't be pushed)

## Step 1: Push to GitHub

```bash
cd d:/magicpin/submission

# If you haven't created a GitHub repo yet, do that first at github.com/new (private OK)
git remote add origin git@github.com:<your-username>/vera-bot.git
git branch -M main
git push -u origin main
```

Verify on github.com that the code is there. Confirm `.env` is **NOT** in the repo (it's gitignored).

## Step 2: Create Render web service

1. Open https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect to GitHub → select your repo
4. Configure:
   - **Name**: `vera-bot` (or similar)
   - **Region**: Singapore (closest to India)
   - **Branch**: `main`
   - **Root directory**: leave blank (the repo is already the bot folder)
   - **Runtime**: Python
   - **Build command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start command**: `uvicorn bot:app --host 0.0.0.0 --port $PORT`
   - **Plan**: **Free**
5. Click **Advanced** → set **Health check path** = `/v1/healthz`

## Step 3: Add environment variables

In the Render Web Service → **Environment** tab → **Add Environment Variable**:

| Key | Value (copy from your local `.env`) |
|---|---|
| `GROQ_API_KEY` | `gsk_...` |
| `GROQ_API_KEY_BACKUP` | `gsk_...` (optional, doubles TPM if set) |
| `SUPABASE_URL` | `https://hmehubbvlqzmdxtacsut.supabase.co` |
| `SUPABASE_DB_HOST` | `aws-1-ap-northeast-1.pooler.supabase.com` |
| `SUPABASE_DB_PORT` | `5432` |
| `SUPABASE_DB_USER` | `postgres.hmehubbvlqzmdxtacsut` |
| `SUPABASE_DB_PASSWORD` | (your Supabase db password) |
| `SUPABASE_DB_NAME` | `postgres` |
| `SUPABASE_SERVICE_KEY` | (your Supabase service-role JWT) |
| `ADMIN_PASSWORD` | (any strong password) |
| `BOT_TEAM_NAME` | `Solo Submission` |
| `BOT_VERSION` | `1.0.0` |
| `BOT_CONTACT_EMAIL` | (your email) |
| `SUPABASE_ENABLED` | `true` |
| `LOG_LEVEL` | `INFO` |
| `LOG_FORMAT` | `json` |
| `PYTHON_VERSION` | `3.11.10` |

**Do NOT put secrets in render.yaml or any committed file.**

## Step 4: Deploy

Click **Create Web Service**. First deploy takes ~3-5 minutes (pip install of dependencies).

## Step 5: Verify the live URL

Render gives you a URL like `https://vera-bot-xxxx.onrender.com`. Test:

```bash
# Healthz
curl https://vera-bot-xxxx.onrender.com/v1/healthz

# Expected: {"status":"ok","uptime_seconds":..., "contexts_loaded":{...}}

# Metadata
curl https://vera-bot-xxxx.onrender.com/v1/metadata

# Push a category
curl -X POST https://vera-bot-xxxx.onrender.com/v1/context \
  -H "Content-Type: application/json" \
  -d '{"scope":"category","context_id":"dentists","version":1,"payload":{"slug":"dentists"},"delivered_at":"2026-05-02T10:00:00Z"}'
```

## Step 6: Set up UptimeRobot (prevents free-tier sleep)

1. Sign up at https://uptimerobot.com (free)
2. **Add New Monitor** → HTTP(s)
3. URL: `https://vera-bot-xxxx.onrender.com/v1/healthz`
4. Monitoring interval: **5 minutes** (free-tier minimum)
5. Alert contact: your email

This keeps the Render service warm for the 3-day live judging window.

## Step 7: Submit URL to magicpin portal

Submit `https://vera-bot-xxxx.onrender.com` (the BASE URL, not the healthz endpoint).

## Troubleshooting

| Issue | Fix |
|---|---|
| Build fails with "no module named X" | Check `requirements.txt` is committed; verify exact package name |
| Bot starts but `/v1/healthz` returns 500 | Check logs in Render Dashboard → Logs tab; usually missing env var |
| Supabase connection error | Verify `SUPABASE_DB_HOST` is the **pooler** hostname (`aws-1-ap-northeast-1.pooler.supabase.com`), not direct (`db.<project>.supabase.co`) |
| 502 / service unreachable | Likely cold start — wait 60s and retry. UptimeRobot will keep it warm. |
| `/v1/tick` returns 500 | Check Groq quota in Render logs; verify `GROQ_API_KEY` is valid |

## Re-deploy after changes

`git push` to `main` auto-triggers a Render deploy (because `autoDeploy: true` in `render.yaml`).
