from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from functools import wraps
from datetime import datetime
import database as db
import ai_helper as ai
import os, json, io, re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))

# Secure session cookies
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7,  # 7 days
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB max upload
)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'.zip', '.tar', '.gz', '.rar', '.7z', '.tar.gz'}

def allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def safe_filename(filename):
    """Sanitize filename — keep only safe characters."""
    name = os.path.basename(filename)
    name = re.sub(r'[^\w\-_\. ]', '', name)
    return name[:100] or 'upload'

# ── Auth decorator ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

# ── Error handlers ─────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'success': False, 'message': 'File too large. Maximum size is 50MB.'}), 413

# ── Public Routes ──────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('intro.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        e = request.form.get('email', '').strip()
        p = request.form.get('password', '')
        c = request.form.get('confirm_password', '')
        if not u or not e or not p:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if len(u) < 3:
            flash('Username must be at least 3 characters.', 'error')
            return render_template('register.html')
        if '@' not in e:
            flash('Please enter a valid email address.', 'error')
            return render_template('register.html')
        if len(p) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('register.html')
        if p != c:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        r = db.register_user(u, e, p)
        if r['success']:
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        flash(r['message'], 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        e = request.form.get('email', '').strip()
        p = request.form.get('password', '')
        if not e or not p:
            flash('Email and password are required.', 'error')
            return render_template('login.html')
        r = db.login_user(e, p)
        if r['success']:
            session.permanent = True
            session['user_id']  = r['user']['id']
            session['username'] = r['user']['username']
            session['email']    = r['user']['email']
            flash(f"Welcome back, {r['user']['username']}!", 'success')
            return redirect(url_for('dashboard'))
        flash(r['message'], 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))

# ── Protected Pages ────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    stats = db.get_dashboard_stats(uid)
    projects = db.get_user_projects(uid)
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    streak = db.get_user_streak(uid)
    return render_template('dashboard.html',
        user=session, stats=stats,
        projects=projects[:5], events=events, tasks=tasks, streak=streak)

@app.route('/projects')
@login_required
def projects():
    uid = session['user_id']
    projs = db.get_user_projects(uid)
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    return render_template('project_manager.html',
        user=session, projects=projs, events=events, tasks=tasks)

@app.route('/schedule')
@login_required
def schedule():
    uid = session['user_id']
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    return render_template('schedule.html', user=session, events=events, tasks=tasks)

@app.route('/notepad')
@login_required
def notepad():
    uid = session['user_id']
    notes = db.get_user_notes(uid)
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    return render_template('notepad.html', user=session, notes=notes, events=events, tasks=tasks)

@app.route('/ai')
@login_required
def ai_page():
    uid = session['user_id']
    stats = db.get_dashboard_stats(uid)
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    return render_template('ai_assistant.html', user=session, stats=stats, events=events, tasks=tasks)

@app.route('/settings')
@login_required
def settings():
    uid = session['user_id']
    profile = db.get_user_profile(uid)
    events = db.get_user_events(uid)
    tasks = db.get_user_tasks(uid)
    return render_template('settings.html', user=session, profile=profile, events=events, tasks=tasks)

# ── API: Projects ──────────────────────────────────────────
@app.route('/api/projects', methods=['GET', 'POST'])
@login_required
def api_projects():
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_user_projects(uid))
    data = request.get_json(silent=True) or {}
    if not data.get('name', '').strip():
        return jsonify({'success': False, 'message': 'Project name is required.'}), 400
    return jsonify(db.create_project(uid, data))

@app.route('/api/projects/<int:pid>', methods=['PUT', 'DELETE'])
@login_required
def api_project(pid):
    uid = session['user_id']
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        return jsonify(db.update_project(uid, pid, data))
    return jsonify(db.delete_project(uid, pid))

@app.route('/api/projects/<int:pid>/tasks', methods=['GET', 'POST'])
@login_required
def api_project_tasks(pid):
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_project_tasks(pid))
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'message': 'Task title is required.'}), 400
    return jsonify(db.add_project_task(uid, pid, title))

@app.route('/api/project-tasks/<int:tid>', methods=['PUT', 'DELETE'])
@login_required
def api_project_task(tid):
    uid = session['user_id']
    if request.method == 'PUT':
        return jsonify(db.toggle_project_task(uid, tid))
    return jsonify(db.delete_project_task(uid, tid))

@app.route('/api/projects/<int:pid>/upload', methods=['POST'])
@login_required
def api_project_upload(pid):
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided.'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'success': False, 'message': 'No file selected.'}), 400
    if not allowed_file(f.filename):
        return jsonify({'success': False, 'message': 'File type not allowed. Upload .zip, .tar, .gz, or .rar files.'}), 400
    uid = session['user_id']
    safe_name = safe_filename(f.filename)
    stored_name = f"proj_{pid}_user_{uid}_{safe_name}"
    save_path = os.path.join(UPLOAD_FOLDER, stored_name)
    f.save(save_path)
    db.update_project(uid, pid, {'zip_file_path': stored_name})
    return jsonify({'success': True, 'filename': safe_name})

@app.route('/api/projects/<int:pid>/download')
@login_required
def api_project_download(pid):
    uid = session['user_id']
    projs = db.get_user_projects(uid)
    proj = next((p for p in projs if p['id'] == pid), None)
    if not proj:
        return jsonify({'success': False, 'message': 'Project not found.'}), 404
    tasks = db.get_project_tasks(pid)
    bundle = {
        'project': proj,
        'checklist': tasks,
        'exported_at': datetime.now().isoformat(),
        'exported_by': session['username'],
    }
    data = json.dumps(bundle, indent=2, default=str).encode()
    safe_name = re.sub(r'[^\w\-]', '_', proj['name'])[:50]
    return send_file(
        io.BytesIO(data), mimetype='application/json',
        as_attachment=True, download_name=f"{safe_name}_devforge_export.json"
    )

# ── API: Tasks ─────────────────────────────────────────────
@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def api_tasks():
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_user_tasks(uid))
    data = request.get_json(silent=True) or {}
    if not data.get('title', '').strip():
        return jsonify({'success': False, 'message': 'Task title is required.'}), 400
    return jsonify(db.create_task(uid, data))

@app.route('/api/tasks/<int:tid>', methods=['PUT', 'DELETE'])
@login_required
def api_task(tid):
    uid = session['user_id']
    if request.method == 'PUT':
        return jsonify(db.update_task(uid, tid, request.get_json(silent=True) or {}))
    return jsonify(db.delete_task(uid, tid))

# ── API: Events ────────────────────────────────────────────
@app.route('/api/events', methods=['GET', 'POST'])
@login_required
def api_events():
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_user_events(uid))
    data = request.get_json(silent=True) or {}
    if not data.get('title', '').strip():
        return jsonify({'success': False, 'message': 'Event title is required.'}), 400
    if not data.get('event_date'):
        return jsonify({'success': False, 'message': 'Event date is required.'}), 400
    return jsonify(db.create_event(uid, data))

@app.route('/api/events/<int:eid>', methods=['PUT', 'DELETE'])
@login_required
def api_event(eid):
    uid = session['user_id']
    if request.method == 'PUT':
        return jsonify(db.update_event(uid, eid, request.get_json(silent=True) or {}))
    return jsonify(db.delete_event(uid, eid))

# ── API: Notes ─────────────────────────────────────────────
@app.route('/api/notes', methods=['GET', 'POST'])
@login_required
def api_notes():
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_user_notes(uid))
    return jsonify(db.create_note(uid, request.get_json(silent=True) or {}))

@app.route('/api/notes/<int:nid>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_note(nid):
    uid = session['user_id']
    if request.method == 'GET':
        note = db.get_note(uid, nid)
        return jsonify(note) if note else (jsonify({'error': 'Not found'}), 404)
    if request.method == 'PUT':
        return jsonify(db.update_note(uid, nid, request.get_json(silent=True) or {}))
    return jsonify(db.delete_note(uid, nid))

# ── API: Profile ───────────────────────────────────────────
@app.route('/api/profile', methods=['GET', 'PUT'])
@login_required
def api_profile():
    uid = session['user_id']
    if request.method == 'GET':
        return jsonify(db.get_user_profile(uid))
    return jsonify(db.update_user_profile(uid, request.get_json(silent=True) or {}))

@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(db.get_dashboard_stats(session['user_id']))

# ── API: AI ────────────────────────────────────────────────
@app.route('/api/ai/summary')
@login_required
def api_ai_summary():
    stats = db.get_dashboard_stats(session['user_id'])
    return jsonify({'success': True, 'result': ai.ai_daily_summary(stats, session['username'])})

@app.route('/api/ai/readme', methods=['POST'])
@login_required
def api_ai_readme():
    data = request.get_json(silent=True) or {}
    return jsonify({'success': True, 'result': ai.ai_generate_readme(
        data.get('name', ''), data.get('description', ''), data.get('tech', '')
    )})

@app.route('/api/ai/improve-description', methods=['POST'])
@login_required
def api_ai_improve():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'result': 'No text provided.'}), 400
    return jsonify({'success': True, 'result': ai.ai_improve_description(text)})

@app.route('/api/ai/task-suggestions', methods=['POST'])
@login_required
def api_ai_tasks():
    data = request.get_json(silent=True) or {}
    return jsonify({'success': True, 'result': ai.ai_task_suggestions(
        data.get('name', ''), data.get('description', ''), data.get('existing_tasks', [])
    )})

@app.route('/api/ai/fix-grammar', methods=['POST'])
@login_required
def api_ai_grammar():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'result': 'No text provided.'}), 400
    return jsonify({'success': True, 'result': ai.ai_fix_grammar(text)})

@app.route('/api/ai/rewrite', methods=['POST'])
@login_required
def api_ai_rewrite():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'result': 'No text provided.'}), 400
    return jsonify({'success': True, 'result': ai.ai_rewrite_professional(text)})

@app.route('/api/ai/summarize', methods=['POST'])
@login_required
def api_ai_summarize():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'result': 'No text provided.'}), 400
    return jsonify({'success': True, 'result': ai.ai_summarize(text)})

@app.route('/api/ai/continue', methods=['POST'])
@login_required
def api_ai_continue():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'result': 'No text provided.'}), 400
    return jsonify({'success': True, 'result': ai.ai_continue_writing(text)})

@app.route('/api/ai/analyze-tasks')
@login_required
def api_ai_analyze():
    tasks = db.get_user_tasks(session['user_id'])
    return jsonify({'success': True, 'result': ai.ai_analyze_tasks(tasks, session['username'])})

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def api_ai_chat():
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'result': 'Empty message.'}), 400
    stats = db.get_dashboard_stats(session['user_id'])
    context = {
        'active_projects': stats.get('active_projects', 0),
        'pending_tasks': stats.get('pending_tasks', 0),
        'completion_rate': stats.get('completion_rate', 0),
    }
    return jsonify({'success': True, 'result': ai.ai_chat(message, context)})

@app.route('/api/ai/generate-resume', methods=['POST'])
@login_required
def api_ai_generate_resume():
    uid = session['user_id']
    profile = db.get_user_profile(uid)
    if not profile:
        return jsonify({'success': False, 'result': 'No profile found.'}), 404
    projects_list = db.get_user_projects(uid)
    finished = [p for p in projects_list if p.get('status') == 'finished']

    parts = []
    name = profile.get('full_name') or profile.get('username', '')
    parts.append(f"# {name}")
    if profile.get('title'):
        parts.append(f"**{profile['title']}**")
    contacts = []
    if profile.get('email'):          contacts.append(f"📧 {profile['email']}")
    if profile.get('phone'):          contacts.append(f"📱 {profile['phone']}")
    if profile.get('location'):       contacts.append(f"📍 {profile['location']}")
    if profile.get('github_profile'): contacts.append(f"🐙 {profile['github_profile']}")
    if profile.get('linkedin_profile'): contacts.append(f"💼 {profile['linkedin_profile']}")
    if profile.get('website'):        contacts.append(f"🌐 {profile['website']}")
    if contacts:
        parts.append(' | '.join(contacts))
    if profile.get('bio'):
        parts.append(f"\n## Summary\n{profile['bio']}")
    if profile.get('skills'):
        parts.append(f"\n## Skills\n{profile['skills']}")
    if profile.get('experience'):
        parts.append(f"\n## Experience\n{profile['experience']}")
    if profile.get('education'):
        parts.append(f"\n## Education\n{profile['education']}")
    if finished:
        parts.append("\n## Projects")
        for p in finished[:6]:
            parts.append(f"### {p['name']}")
            if p.get('description'): parts.append(p['description'])
            if p.get('tech'):        parts.append(f"**Tech:** {p['tech']}")
            if p.get('github_url'):  parts.append(f"**GitHub:** {p['github_url']}")

    return jsonify({'success': True, 'result': '\n\n'.join(parts)})


@app.route('/api/ai/code-review', methods=['POST'])
@login_required
def api_ai_code_review():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'result': 'No code provided.'}), 400
    if len(code) > 8000:
        return jsonify({'success': False, 'result': 'Code too long. Please paste up to ~8000 characters.'}), 400
    return jsonify({'success': True, 'result': ai.ai_code_review(code, data.get('language', ''))})

@app.route('/api/ai/pomodoro-tip')
@login_required
def api_ai_pomodoro_tip():
    tasks = db.get_user_tasks(session['user_id'])
    return jsonify({'success': True, 'result': ai.ai_pomodoro_tip(session['username'], tasks)})


if __name__ == '__main__':
    db.init_db()
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
