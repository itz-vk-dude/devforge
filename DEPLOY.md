# 🚀 DevForge — Free Deployment Guide

This guide covers deploying DevForge for free on popular platforms.

---

## Option 1 — Railway (Recommended, Easiest)

Railway gives you $5/month free credit — more than enough for a small app with a few users.

1. Push your code to a GitHub repository
2. Go to [railway.app](https://railway.app) and sign up with GitHub
3. Click **New Project → Deploy from GitHub repo**
4. Select your DevForge repo
5. Add a **PostgreSQL** plugin (Railway provisions it automatically)
6. Set environment variables in the Railway dashboard:
   ```
   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
   PASSWORD_SALT=<generate same way>
   OPENROUTER_API_KEY=<optional, from openrouter.ai>
   FLASK_ENV=production
   APP_URL=https://your-app.up.railway.app
   ```
7. Railway auto-detects the `Procfile` and deploys. Done!

> **DB vars** (`DB_HOST`, `DB_USER`, etc.) are injected automatically from the PostgreSQL plugin.

---

## Option 2 — Render

Render's free tier works but spins down after inactivity. Good for demos.

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your repo. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn wsgi:app --workers 2 --bind 0.0.0.0:$PORT`
5. Add a **PostgreSQL** database (free tier)
6. Add environment variables (same as Railway above)
7. Deploy!

---

## Option 3 — Docker (VPS / Any server)

Works on any VPS with Docker (e.g. DigitalOcean $4/mo, Hetzner €3/mo, Oracle Cloud Free Tier).

```bash
# 1. Clone your repo on the server
git clone https://github.com/yourusername/devforge.git
cd devforge

# 2. Set secrets
cp .env.example .env
nano .env   # Fill in SECRET_KEY, PASSWORD_SALT, OPENROUTER_API_KEY

# 3. Launch
docker compose up -d

# 4. App is running at http://your-server-ip:8000
```

For HTTPS, put Nginx + Certbot in front:
```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Option 4 — Fly.io (Free Tier)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch   # follow prompts
fly postgres create --name devforge-db
fly postgres attach devforge-db
fly secrets set SECRET_KEY=... PASSWORD_SALT=...
fly deploy
```

---

## AI Features (Free)

DevForge uses [OpenRouter](https://openrouter.ai) for AI, which gives free credits on signup.

1. Sign up at openrouter.ai
2. Create an API key
3. Set `OPENROUTER_API_KEY` in your environment

The default model (`mistralai/mistral-7b-instruct`) is very cheap — roughly $0.001 per request.

---

## Environment Variable Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Random 32-byte hex — never reuse across deployments |
| `PASSWORD_SALT` | ✅ | Random 32-byte hex — changing this invalidates all passwords |
| `DB_HOST` | ✅ | PostgreSQL host |
| `DB_USER` | ✅ | PostgreSQL user |
| `DB_PASSWORD` | ✅ | PostgreSQL password |
| `DB_NAME` | ✅ | Database name (auto-created) |
| `OPENROUTER_API_KEY` | No | Enables AI features |
| `FLASK_ENV` | No | Set to `production` for live deployment |
| `APP_URL` | No | Your public URL (used in AI request headers) |

---

## What's New in v3.1

- 🔥 **Daily Streak** tracker on the dashboard (replaces Notes stat card)
- 🍅 **Pomodoro Timer** with AI focus suggestions on the dashboard
- 🔍 **AI Code Review** tool in the AI Assistant (bugs, security, best practices)
- 🐳 **Docker + docker-compose** for one-command deployment
- 🚀 This deploy guide
