import psycopg2
import psycopg2.extras
import psycopg2.pool
import hashlib
import hmac
import os
from datetime import datetime, date

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'dbname':   os.environ.get('DB_NAME', 'devforge'),
    'port':     int(os.environ.get('DB_PORT', 5432)),
}

# Connection pool (2–10 connections)
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, **DB_CONFIG)
    return _pool

def get_connection():
    return get_pool().getconn()

def release_connection(conn):
    get_pool().putconn(conn)

# ── Password hashing ───────────────────────────────────────
# Using PBKDF2-HMAC-SHA256 (no extra dependencies, strong enough)
_SALT = os.environ.get('PASSWORD_SALT', 'devforge-default-salt-change-in-production').encode()

def _hash(password: str) -> str:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), _SALT, 260000)
    return dk.hex()

def _verify(password: str, stored: str) -> bool:
    return hmac.compare_digest(_hash(password), stored)

# ── Serialization helper ───────────────────────────────────
def _s(row):
    if not row:
        return row
    if isinstance(row, dict):
        return {k: str(v) if isinstance(v, (date, datetime)) else v for k, v in row.items()}
    return row

# ── Database Init ──────────────────────────────────────────
def init_db():
    # Try to create the database if it doesn't exist
    try:
        cfg = {**DB_CONFIG, 'dbname': 'postgres'}
        conn = psycopg2.connect(**cfg)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_CONFIG['dbname']}'")
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
            print(f"[DevForge] Created database '{DB_CONFIG['dbname']}'")
        cur.close(); conn.close()
    except Exception as e:
        print(f"[DevForge] DB create notice: {e}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(80) NOT NULL UNIQUE,
        email VARCHAR(120) NOT NULL UNIQUE,
        password VARCHAR(128) NOT NULL,
        full_name VARCHAR(200),
        phone VARCHAR(30),
        location VARCHAR(200),
        bio TEXT,
        title VARCHAR(200),
        skills TEXT,
        experience TEXT,
        education TEXT,
        github_profile VARCHAR(300),
        linkedin_profile VARCHAR(300),
        website VARCHAR(300),
        avatar_color VARCHAR(20) DEFAULT '#6ee7b7',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS projects (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        status VARCHAR(20) DEFAULT 'planning' CHECK(status IN ('planning','in_progress','finished')),
        tech VARCHAR(500),
        progress INT DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
        github_url VARCHAR(500),
        readme_text TEXT,
        start_date DATE,
        end_date DATE,
        zip_file_path VARCHAR(500),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS project_tasks (
        id SERIAL PRIMARY KEY,
        project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(300) NOT NULL,
        done BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        project_id INT REFERENCES projects(id) ON DELETE SET NULL,
        title VARCHAR(300) NOT NULL,
        done BOOLEAN DEFAULT FALSE,
        priority VARCHAR(10) DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
        due_date DATE,
        status VARCHAR(10) DEFAULT 'pending' CHECK(status IN ('pending','done','missed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(300) NOT NULL,
        description TEXT,
        event_date DATE NOT NULL,
        event_time TIME,
        type VARCHAR(20) DEFAULT 'other',
        repeat_rule VARCHAR(50) DEFAULT 'none',
        notify BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(300) NOT NULL,
        content TEXT,
        color VARCHAR(20) DEFAULT '#141926',
        pinned BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Add missing columns to existing tables (safe migrations)
    _safe_add_column(cur, 'events', 'notify', 'BOOLEAN DEFAULT FALSE')
    _safe_add_column(cur, 'projects', 'zip_file_path', 'VARCHAR(500)')

    cur.close(); conn.close()
    print("[DevForge] PostgreSQL database initialised ✓")

def _safe_add_column(cur, table, column, definition):
    """Add column only if it doesn't exist (safe migration)."""
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

# ── Users ──────────────────────────────────────────────────
def register_user(username, email, password):
    if len(password) < 8:
        return {'success': False, 'message': 'Password must be at least 8 characters.'}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",
            (username.strip(), email.strip().lower(), _hash(password))
        )
        conn.commit(); cur.close()
        return {'success': True}
    except psycopg2.IntegrityError as e:
        conn.rollback()
        if 'username' in str(e):
            return {'success': False, 'message': 'Username already taken.'}
        return {'success': False, 'message': 'Email already registered.'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': 'Registration failed. Please try again.'}
    finally:
        release_connection(conn)

def login_user(email, password):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, username, email, password FROM users WHERE email=%s",
            (email.strip().lower(),)
        )
        user = cur.fetchone(); cur.close()
        if user and _verify(password, user['password']):
            return {'success': True, 'user': {
                'id': user['id'], 'username': user['username'], 'email': user['email']
            }}
        return {'success': False, 'message': 'Invalid email or password.'}
    except Exception as e:
        return {'success': False, 'message': 'Login failed. Please try again.'}
    finally:
        release_connection(conn)

def get_user_profile(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone(); cur.close()
        return _s(dict(row)) if row else None
    finally:
        release_connection(conn)

def update_user_profile(user_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""UPDATE users SET
            full_name=%s, phone=%s, location=%s, bio=%s, title=%s,
            skills=%s, experience=%s, education=%s,
            github_profile=%s, linkedin_profile=%s, website=%s, avatar_color=%s
            WHERE id=%s""",
            (
                data.get('full_name'), data.get('phone'), data.get('location'),
                data.get('bio'), data.get('title'), data.get('skills'),
                data.get('experience'), data.get('education'),
                data.get('github_profile'), data.get('linkedin_profile'),
                data.get('website'), data.get('avatar_color', '#6ee7b7'),
                user_id
            )
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Projects ───────────────────────────────────────────────
def get_user_projects(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM projects WHERE user_id=%s ORDER BY updated_at DESC", (user_id,))
        rows = cur.fetchall(); cur.close()
        return [_s(dict(r)) for r in rows]
    finally:
        release_connection(conn)

def create_project(user_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO projects(user_id,name,description,status,tech,progress,github_url,start_date)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                user_id, data.get('name', 'Untitled'),
                data.get('description', ''), data.get('status', 'planning'),
                data.get('tech', ''), max(0, min(100, int(data.get('progress', 0)))),
                data.get('github_url', ''), data.get('start_date') or None
            )
        )
        pid = cur.fetchone()[0]
        for t in data.get('tasks', []):
            if t.get('text', '').strip():
                cur.execute(
                    "INSERT INTO project_tasks(project_id,user_id,title,done) VALUES(%s,%s,%s,%s)",
                    (pid, user_id, t['text'].strip(), bool(t.get('done', False)))
                )
        conn.commit(); cur.close()
        return {'success': True, 'id': pid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def update_project(user_id, project_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""UPDATE projects SET
            name=%s, description=%s, status=%s, tech=%s, progress=%s,
            github_url=%s, readme_text=%s, end_date=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s AND user_id=%s""",
            (
                data.get('name'), data.get('description', ''),
                data.get('status', 'planning'), data.get('tech', ''),
                max(0, min(100, int(data.get('progress', 0)))),
                data.get('github_url', ''), data.get('readme_text', ''),
                data.get('end_date') or None, project_id, user_id
            )
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def delete_project(user_id, project_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE id=%s AND user_id=%s", (project_id, user_id))
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Project Tasks (Checklist) ──────────────────────────────
def get_project_tasks(project_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM project_tasks WHERE project_id=%s ORDER BY id ASC", (project_id,))
        rows = cur.fetchall(); cur.close()
        return [_s(dict(r)) for r in rows]
    finally:
        release_connection(conn)

def add_project_task(user_id, project_id, title):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_tasks(project_id,user_id,title) VALUES(%s,%s,%s) RETURNING id",
            (project_id, user_id, title.strip())
        )
        tid = cur.fetchone()[0]; conn.commit(); cur.close()
        return {'success': True, 'id': tid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def toggle_project_task(user_id, task_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE project_tasks SET done = NOT done WHERE id=%s AND user_id=%s",
            (task_id, user_id)
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def delete_project_task(user_id, task_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_tasks WHERE id=%s AND user_id=%s", (task_id, user_id))
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Tasks ──────────────────────────────────────────────────
def get_user_tasks(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Auto-mark overdue tasks
        cur.execute("""UPDATE tasks SET status='missed'
            WHERE user_id=%s AND done=FALSE AND due_date < CURRENT_DATE AND status='pending'""",
            (user_id,)
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM tasks WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall(); conn.commit(); cur.close()
        return [_s(dict(r)) for r in rows]
    finally:
        release_connection(conn)

def create_task(user_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO tasks(user_id,project_id,title,priority,due_date)
            VALUES(%s,%s,%s,%s,%s) RETURNING id""",
            (
                user_id, data.get('project_id') or None,
                data.get('title', '').strip(),
                data.get('priority', 'medium'),
                data.get('due_date') or None
            )
        )
        tid = cur.fetchone()[0]; conn.commit(); cur.close()
        return {'success': True, 'id': tid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def update_task(user_id, task_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        done = bool(data.get('done', False))
        status = data.get('status', 'done' if done else 'pending')
        cur.execute("""UPDATE tasks SET title=%s, done=%s, priority=%s,
            due_date=%s, project_id=%s, status=%s WHERE id=%s AND user_id=%s""",
            (
                data.get('title', '').strip(), done,
                data.get('priority', 'medium'), data.get('due_date') or None,
                data.get('project_id') or None, status, task_id, user_id
            )
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def delete_task(user_id, task_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tasks WHERE id=%s AND user_id=%s", (task_id, user_id))
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Events ─────────────────────────────────────────────────
def get_user_events(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM events WHERE user_id=%s ORDER BY event_date ASC, event_time ASC",
            (user_id,)
        )
        rows = cur.fetchall(); cur.close()
        return [_s(dict(r)) for r in rows]
    finally:
        release_connection(conn)

def create_event(user_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO events(user_id,title,description,event_date,event_time,type,repeat_rule,notify)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                user_id, data.get('title', '').strip(),
                data.get('description', ''), data.get('event_date'),
                data.get('event_time') or None, data.get('type', 'other'),
                data.get('repeat_rule', 'none'), bool(data.get('notify', False))
            )
        )
        eid = cur.fetchone()[0]; conn.commit(); cur.close()
        return {'success': True, 'id': eid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def update_event(user_id, event_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""UPDATE events SET title=%s, description=%s, event_date=%s,
            event_time=%s, type=%s, repeat_rule=%s, notify=%s WHERE id=%s AND user_id=%s""",
            (
                data.get('title', '').strip(), data.get('description', ''),
                data.get('event_date'), data.get('event_time') or None,
                data.get('type', 'other'), data.get('repeat_rule', 'none'),
                bool(data.get('notify', False)), event_id, user_id
            )
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def delete_event(user_id, event_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id=%s AND user_id=%s", (event_id, user_id))
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Notes ──────────────────────────────────────────────────
def get_user_notes(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM notes WHERE user_id=%s ORDER BY pinned DESC, updated_at DESC",
            (user_id,)
        )
        rows = cur.fetchall(); cur.close()
        return [_s(dict(r)) for r in rows]
    finally:
        release_connection(conn)

def get_note(user_id, note_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM notes WHERE id=%s AND user_id=%s", (note_id, user_id))
        row = cur.fetchone(); cur.close()
        return _s(dict(row)) if row else None
    finally:
        release_connection(conn)

def create_note(user_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notes(user_id,title,content,color,pinned) VALUES(%s,%s,%s,%s,%s) RETURNING id",
            (
                user_id, data.get('title', 'Untitled'),
                data.get('content', ''), data.get('color', '#141926'),
                bool(data.get('pinned', False))
            )
        )
        nid = cur.fetchone()[0]; conn.commit(); cur.close()
        return {'success': True, 'id': nid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def update_note(user_id, note_id, data):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""UPDATE notes SET title=%s, content=%s, color=%s, pinned=%s,
            updated_at=CURRENT_TIMESTAMP WHERE id=%s AND user_id=%s""",
            (
                data.get('title', 'Untitled'), data.get('content', ''),
                data.get('color', '#141926'), bool(data.get('pinned', False)),
                note_id, user_id
            )
        )
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

def delete_note(user_id, note_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM notes WHERE id=%s AND user_id=%s", (note_id, user_id))
        conn.commit(); cur.close()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        release_connection(conn)

# ── Streaks ────────────────────────────────────────────────
def get_user_streak(user_id):
    """Returns current daily streak (days with at least 1 completed task)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DATE(created_at) as day
            FROM tasks
            WHERE user_id=%s AND done=TRUE
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """, (user_id,))
        rows = cur.fetchall(); cur.close()
        if not rows:
            return 0
        streak = 0
        from datetime import date, timedelta
        check = date.today()
        for (day,) in rows:
            if isinstance(day, str):
                from datetime import datetime
                day = datetime.strptime(day, '%Y-%m-%d').date()
            if day == check or (streak == 0 and day == check - timedelta(days=1)):
                streak += 1
                check = day - timedelta(days=1)
            elif day < check:
                break
        return streak
    finally:
        release_connection(conn)


# ── Dashboard Stats ────────────────────────────────────────
def get_dashboard_stats(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        def q(sql, args=()):
            cur.execute(sql, args)
            row = cur.fetchone()
            return row['v'] if row else 0

        total_projects    = q("SELECT COUNT(*) as v FROM projects WHERE user_id=%s", (user_id,))
        active_projects   = q("SELECT COUNT(*) as v FROM projects WHERE user_id=%s AND status='in_progress'", (user_id,))
        finished_projects = q("SELECT COUNT(*) as v FROM projects WHERE user_id=%s AND status='finished'", (user_id,))
        tasks_done_today  = q("SELECT COUNT(*) as v FROM tasks WHERE user_id=%s AND done=TRUE AND DATE(created_at)=CURRENT_DATE", (user_id,))
        pending_tasks     = q("SELECT COUNT(*) as v FROM tasks WHERE user_id=%s AND done=FALSE AND status='pending'", (user_id,))
        missed_tasks      = q("SELECT COUNT(*) as v FROM tasks WHERE user_id=%s AND status='missed'", (user_id,))
        total_tasks       = q("SELECT COUNT(*) as v FROM tasks WHERE user_id=%s", (user_id,))
        done_tasks        = q("SELECT COUNT(*) as v FROM tasks WHERE user_id=%s AND done=TRUE", (user_id,))
        total_notes       = q("SELECT COUNT(*) as v FROM notes WHERE user_id=%s", (user_id,))

        cur.execute("""SELECT * FROM events WHERE user_id=%s AND event_date >= CURRENT_DATE
            ORDER BY event_date ASC, event_time ASC LIMIT 5""", (user_id,))
        upcoming_events = [_s(dict(r)) for r in cur.fetchall()]

        cur.execute("""SELECT * FROM tasks WHERE user_id=%s AND done=FALSE
            AND due_date <= CURRENT_DATE ORDER BY due_date ASC LIMIT 5""", (user_id,))
        due_tasks = [_s(dict(r)) for r in cur.fetchall()]

        cur.execute("""SELECT EXTRACT(DOW FROM created_at)::int as day, COUNT(*) as cnt
            FROM tasks WHERE user_id=%s AND done=TRUE AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY EXTRACT(DOW FROM created_at)::int""", (user_id,))
        prod_by_day = {str(r['day']): int(r['cnt']) for r in cur.fetchall()}

        cur.close()
        return {
            'total_projects':    total_projects,
            'active_projects':   active_projects,
            'finished_projects': finished_projects,
            'tasks_done_today':  tasks_done_today,
            'pending_tasks':     pending_tasks,
            'missed_tasks':      missed_tasks,
            'total_tasks':       total_tasks,
            'done_tasks':        done_tasks,
            'total_notes':       total_notes,
            'completion_rate':   round((done_tasks / total_tasks * 100) if total_tasks else 0),
            'upcoming_events':   upcoming_events,
            'due_tasks':         due_tasks,
            'prod_by_day':       prod_by_day,
        }
    finally:
        release_connection(conn)
