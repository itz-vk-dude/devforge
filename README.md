# DevForge — Modern Developer Workspace

> A full-stack developer productivity app built with Flask and PostgreSQL. Beautifully designed, feature-complete, and ready for real-world deployment.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🎨 **6 Themes** | Dark, Light, Ocean, Violet, Sunset, Forest |
| 📱 **Responsive** | Mobile, tablet, laptop — fully adaptive |
| ⏰ **Live Clock** | Real-time AM/PM clock everywhere |
| ◫ **Projects** | Checklist ✓, GitHub links 🐙, README editor, file upload/download |
| ◷ **Schedule** | Calendar, AM/PM events, Yearly repeat, Browser notifications |
| ✎ **Notepad** | Rich editor, pinning, color labels, AI tools, inline checklist |
| ✦ **AI Assistant** | Chat, summarize, rewrite, grammar fix, README/resume generator |
| 👤 **Profile** | Full biodata, avatar, AI-generated resume download |
| 🔔 **Notifications** | Panel + browser push notifications (15 min before events) |

---

## 🚀 Quick Start (Local)

### 1. Prerequisites
- Python 3.9+
- PostgreSQL 13+

### 2. Clone & install
```bash
git clone https://github.com/yourusername/devforge.git
cd devforge
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials and secret key
```

### 4. Run
```bash
python app.py
```
Open `http://localhost:5000`

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ Yes | Random secret for sessions — use `python -c "import secrets; print(secrets.token_hex(32))"` |
| `PASSWORD_SALT` | ✅ Yes | Salt for password hashing — generate same way |
| `DB_HOST` | ✅ Yes | PostgreSQL host |
| `DB_USER` | ✅ Yes | PostgreSQL user |
| `DB_PASSWORD` | ✅ Yes | PostgreSQL password |
| `DB_NAME` | ✅ Yes | Database name (auto-created if missing) |
| `DB_PORT` | No | Default: `5432` |
| `OPENROUTER_API_KEY` | No | AI features (get at openrouter.ai) |
| `FLASK_ENV` | No | Set to `production` for live deployment |
| `PORT` | No | Server port (default `5000`) |

---

## 🌐 Production Deployment

### Option A — Railway / Render / Fly.io (easiest)
1. Push code to GitHub
2. Connect repo on Railway/Render
3. Add environment variables in dashboard
4. Deploy — done!

### Option B — VPS (Ubuntu)
```bash
# Install dependencies
sudo apt install python3 python3-pip postgresql nginx

# Setup PostgreSQL
sudo -u postgres createuser devforge_user
sudo -u postgres createdb devforge -O devforge_user
sudo -u postgres psql -c "ALTER USER devforge_user PASSWORD 'yourpassword';"

# Clone and configure
git clone https://github.com/yourusername/devforge.git /var/www/devforge
cd /var/www/devforge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # fill in your values

# Run with gunicorn
gunicorn wsgi:app --workers 4 --bind 127.0.0.1:8000 --daemon

# Configure Nginx
sudo nano /etc/nginx/sites-available/devforge
```

Nginx config:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /var/www/devforge/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    client_max_body_size 50M;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/devforge /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# Then add HTTPS with: sudo certbot --nginx -d yourdomain.com
```

### Option C — Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "wsgi:app", "--workers", "4", "--bind", "0.0.0.0:8000"]
```

---

## 🔒 Security Notes

- Passwords are hashed with PBKDF2-HMAC-SHA256 (260,000 iterations)
- Set a unique `SECRET_KEY` and `PASSWORD_SALT` per deployment
- Use HTTPS in production (enables secure cookies + browser notifications)
- File uploads are validated and sanitized
- All DB queries use parameterized statements (no SQL injection)

---

## 📂 Project Structure

```
devforge/
├── app.py               # Flask routes & API endpoints
├── database.py          # PostgreSQL queries with connection pooling
├── ai_helper.py         # OpenRouter AI integration
├── wsgi.py              # Gunicorn entry point
├── requirements.txt
├── .env.example
├── Procfile             # For Railway/Heroku
├── static/
│   ├── css/main.css     # Full design system (6 themes, responsive)
│   └── js/cursor.js     # Cursor, clock, theme, notifications
├── templates/
│   ├── base.html        # Base layout (injects events/tasks to all pages)
│   ├── sidebar.html     # Reusable sidebar macro
│   ├── dashboard.html   # Dashboard with clock widget & stats
│   ├── project_manager.html  # Projects with checklist, GitHub, upload, README
│   ├── schedule.html    # Calendar, AM/PM events, kanban, yearly repeat
│   ├── notepad.html     # Rich editor with checklist & AI tools
│   ├── ai_assistant.html  # AI chat & content tools
│   ├── settings.html    # Profile, biodata, resume generator
│   ├── login.html
│   ├── register.html
│   ├── intro.html
│   ├── 404.html
│   └── 500.html
└── uploads/             # Project file uploads (gitignored)
```

---

## 🎨 Theme Reference

| Theme | Base | Accent |
|-------|------|--------|
| Dark | `#0a0d14` | Mint `#6ee7b7` |
| Light | `#f0f2f8` | Emerald `#059669` |
| Ocean | `#040d1a` | Sky `#38bdf8` |
| Violet | `#0d0a1a` | Purple `#a78bfa` |
| Sunset | `#160a08` | Orange `#fb923c` |
| Forest | `#060e08` | Green `#4ade80` |

---

## 📝 License

MIT — free to use, modify, and deploy.
