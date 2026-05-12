from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import aiosqlite
import asyncio
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB_PATH = "neko_bot/neko.db"
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", 5001))
API_SECRET = os.environ.get("DASHBOARD_SECRET", "neko_dashboard_secret")


def db():
    return sqlite3.connect(DB_PATH)


def require_secret():
    secret = request.headers.get("X-Dashboard-Secret", "")
    if secret != API_SECRET:
        abort(401)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/guilds/<guild_id>/stats")
def guild_stats(guild_id):
    require_secret()
    con = db()
    cur = con.cursor()
    total_users = cur.execute("SELECT COUNT(*) FROM users WHERE guild_id = ?", (guild_id,)).fetchone()[0]
    total_messages = cur.execute("SELECT SUM(messages) FROM users WHERE guild_id = ?", (guild_id,)).fetchone()[0] or 0
    top_level = cur.execute("SELECT MAX(level) FROM users WHERE guild_id = ?", (guild_id,)).fetchone()[0] or 0
    mod_actions = cur.execute("SELECT COUNT(*) FROM mod_logs WHERE guild_id = ?", (guild_id,)).fetchone()[0]
    con.close()
    return jsonify({
        "total_users": total_users,
        "total_messages": total_messages,
        "top_level": top_level,
        "mod_actions": mod_actions,
    })


@app.route("/api/guilds/<guild_id>/ranking")
def guild_ranking(guild_id):
    require_secret()
    con = db()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT user_id, username, level, xp, messages FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 20",
        (guild_id,)
    ).fetchall()
    con.close()
    return jsonify([
        {"user_id": r[0], "username": r[1], "level": r[2], "xp": r[3], "messages": r[4]}
        for r in rows
    ])


@app.route("/api/guilds/<guild_id>/settings", methods=["GET"])
def get_settings(guild_id):
    require_secret()
    con = db()
    cur = con.cursor()
    row = cur.execute(
        "SELECT prefix, welcome_channel, welcome_message, log_channel, xp_enabled, mod_role FROM guild_settings WHERE guild_id = ?",
        (guild_id,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify({"prefix": "n!", "welcome_channel": "", "welcome_message": "", "log_channel": "", "xp_enabled": 1, "mod_role": ""})
    return jsonify({
        "prefix": row[0], "welcome_channel": row[1] or "", "welcome_message": row[2] or "",
        "log_channel": row[3] or "", "xp_enabled": row[4], "mod_role": row[5] or ""
    })


@app.route("/api/guilds/<guild_id>/settings", methods=["POST"])
def update_settings(guild_id):
    require_secret()
    data = request.get_json()
    allowed = ["prefix", "welcome_channel", "welcome_message", "log_channel", "xp_enabled", "mod_role"]
    con = db()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
    for key in allowed:
        if key in data:
            cur.execute(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (data[key], guild_id))
    con.commit()
    con.close()
    return jsonify({"success": True})


@app.route("/api/guilds/<guild_id>/modlogs")
def mod_logs(guild_id):
    require_secret()
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page
    con = db()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT action, moderator_name, target_name, reason, timestamp FROM mod_logs WHERE guild_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (guild_id, per_page, offset)
    ).fetchall()
    total = cur.execute("SELECT COUNT(*) FROM mod_logs WHERE guild_id = ?", (guild_id,)).fetchone()[0]
    con.close()
    return jsonify({
        "total": total,
        "page": page,
        "logs": [{"action": r[0], "moderator": r[1], "target": r[2], "reason": r[3], "timestamp": r[4]} for r in rows]
    })


@app.route("/api/guilds/<guild_id>/users")
def guild_users(guild_id):
    require_secret()
    con = db()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT user_id, username, xp, level, messages FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC",
        (guild_id,)
    ).fetchall()
    con.close()
    return jsonify([
        {"user_id": r[0], "username": r[1], "xp": r[2], "level": r[3], "messages": r[4]}
        for r in rows
    ])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)
