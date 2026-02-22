import os
import requests

# =====================================================
# OpenRouter AI Helper — DevForge
# Set OPENROUTER_API_KEY in your .env file
# =====================================================

API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL   = "mistralai/mistral-7b-instruct"

def _chat(system_prompt, user_prompt, max_tokens=400):
    if not API_KEY:
        return "AI features require an OpenRouter API key. Add OPENROUTER_API_KEY to your .env file."
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  os.environ.get('APP_URL', 'http://localhost:5000'),
        "X-Title":       "DevForge",
    }
    try:
        payload = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }
        r = requests.post(API_URL, headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        return "AI is taking too long to respond. Please try again."
    except requests.exceptions.HTTPError as e:
        return f"API error {e.response.status_code}. Check your OpenRouter API key."
    except Exception as e:
        return f"AI unavailable: {str(e)}"


def ai_daily_summary(stats, username):
    system = (
        "You are DevForge AI, a smart productivity assistant for developers. "
        "Be concise, motivational, and practical. Respond in 2-3 sentences max."
    )
    user = (
        f"Generate a daily summary for developer '{username}':\n"
        f"- Active projects: {stats.get('active_projects', 0)}\n"
        f"- Finished projects: {stats.get('finished_projects', 0)}\n"
        f"- Tasks done today: {stats.get('tasks_done_today', 0)}\n"
        f"- Pending tasks: {stats.get('pending_tasks', 0)}\n"
        f"- Missed deadlines: {stats.get('missed_tasks', 0)}\n"
        f"- Completion rate: {stats.get('completion_rate', 0)}%\n"
        "Give a friendly summary with one actionable tip."
    )
    return _chat(system, user, max_tokens=150)


def ai_generate_readme(project_name, description, tech):
    system = (
        "You are a senior developer. Write a complete, professional README.md "
        "with sections: Overview, Features, Tech Stack, Setup, Usage. Use markdown."
    )
    user = (
        f"Project: {project_name}\n"
        f"Description: {description}\n"
        f"Tech/Language: {tech}\n"
        "Write the full README.md now."
    )
    return _chat(system, user, max_tokens=700)


def ai_improve_description(text):
    system = (
        "You are a technical writer. Improve the project description to be clear, "
        "professional and concise. Return ONLY the improved text, nothing else."
    )
    return _chat(system, f"Improve this:\n{text}", max_tokens=200)


def ai_task_suggestions(project_name, description, existing_tasks):
    system = (
        "You are a software architect. Suggest specific, actionable development tasks "
        "as a numbered list. Max 6 tasks. Be concrete, not generic."
    )
    existing = ", ".join(existing_tasks) if existing_tasks else "none yet"
    user = (
        f"Project: {project_name}\n"
        f"Description: {description}\n"
        f"Existing tasks: {existing}\n"
        "Suggest the next 5-6 development tasks."
    )
    return _chat(system, user, max_tokens=300)


def ai_fix_grammar(text):
    system = (
        "You are a grammar assistant. Fix grammar, spelling, punctuation and clarity. "
        "Return ONLY the corrected text, nothing else."
    )
    return _chat(system, f"Fix grammar:\n{text}", max_tokens=400)


def ai_rewrite_professional(text):
    system = (
        "You are a professional technical writer. Rewrite in a professional, formal tone. "
        "Return ONLY the rewritten text, nothing else."
    )
    return _chat(system, f"Rewrite professionally:\n{text}", max_tokens=400)


def ai_summarize(text):
    system = (
        "You are a concise summarizer. Summarize in 2-3 sentences. "
        "Return ONLY the summary, nothing else."
    )
    return _chat(system, f"Summarize:\n{text}", max_tokens=150)


def ai_continue_writing(text):
    system = (
        "You are a writing assistant. Continue the text naturally with 2-3 more sentences. "
        "Return ONLY the continuation text, nothing else."
    )
    return _chat(system, f"Continue this:\n{text}", max_tokens=200)


def ai_analyze_tasks(tasks, username):
    system = (
        "You are a productivity coach for developers. Give 2-3 specific, actionable "
        "insights about their task patterns. Be direct and helpful."
    )
    done   = [t for t in tasks if t.get("done")]
    missed = [t for t in tasks if t.get("status") == "missed"]
    high   = [t for t in tasks if t.get("priority") == "high" and not t.get("done")]
    user = (
        f"Developer: {username}\n"
        f"Total tasks: {len(tasks)}, Completed: {len(done)}, Missed: {len(missed)}\n"
        f"High-priority pending: {len(high)}\n"
        f"Recent completed: {[t['title'] for t in done[-5:]]}\n"
        f"Missed: {[t['title'] for t in missed[-3:]]}\n"
        "Give 2-3 productivity insights."
    )
    return _chat(system, user, max_tokens=250)


def ai_code_review(code, language=''):
    system = (
        "You are a senior code reviewer. Review the code for: bugs, security issues, "
        "performance problems, and style/best practices. Be concise. Format your response as:\n"
        "**Issues:** (list any bugs or problems)\n"
        "**Suggestions:** (improvements)\n"
        "**Verdict:** (one sentence overall assessment)\n"
        "If the code looks good, say so. Keep the total response under 250 words."
    )
    lang_note = f"Language: {language}\n" if language else ""
    return _chat(system, f"{lang_note}Review this code:\n```\n{code}\n```", max_tokens=500)


def ai_pomodoro_tip(username, tasks):
    system = (
        "You are a focus coach. Given a list of pending tasks, suggest which ONE task "
        "to work on in the next 25-minute Pomodoro session, and why. Be very brief (2 sentences max)."
    )
    task_names = [t.get('title', '') for t in tasks[:8] if not t.get('done')]
    task_list = ', '.join(task_names) if task_names else 'no pending tasks'
    return _chat(system, f"Pending tasks for {username}: {task_list}\nRecommend the best Pomodoro focus task.", max_tokens=100)


def ai_chat(message, context):
    system = (
        "You are DevForge AI, a helpful assistant inside a developer productivity app. "
        "Help with project planning, coding questions, task management, and writing. "
        "Be concise and practical. Keep responses under 5 sentences unless asked for more."
    )
    ctx = (
        f"User context: {context.get('active_projects', 0)} active projects, "
        f"{context.get('pending_tasks', 0)} pending tasks, "
        f"{context.get('completion_rate', 0)}% completion rate."
    )
    return _chat(system, f"{ctx}\n\nUser: {message}", max_tokens=400)
