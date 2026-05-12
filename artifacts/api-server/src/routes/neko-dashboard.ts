import { Router } from "express";
import { execFileSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const router = Router();

const SECRET = process.env["DASHBOARD_SECRET"] || "neko_dashboard_secret";
const DB_PATH = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../neko_bot/neko.db");

function requireSecret(req: any, res: any): boolean {
  const secret = req.headers["x-dashboard-secret"] || "";
  if (secret !== SECRET) {
    res.status(401).json({ error: "Unauthorized" });
    return false;
  }
  return true;
}

function queryDb(sql: string, params: (string | number)[] = []): any[] {
  const script = `
import sqlite3, json, sys
db = sqlite3.connect(${JSON.stringify(DB_PATH)})
db.row_factory = sqlite3.Row
params = json.loads(sys.argv[1])
rows = db.execute(${JSON.stringify(sql)}, params).fetchall()
print(json.dumps([dict(r) for r in rows]))
db.close()
`;
  const out = execFileSync("python3", ["-c", script, JSON.stringify(params)], { encoding: "utf8" });
  return JSON.parse(out.trim());
}

function queryDbOne(sql: string, params: (string | number)[] = []): any {
  const rows = queryDb(sql, params);
  return rows[0] ?? null;
}

function execDb(sql: string, params: (string | number)[] = []): void {
  const script = `
import sqlite3, json, sys
db = sqlite3.connect(${JSON.stringify(DB_PATH)})
params = json.loads(sys.argv[1])
db.execute(${JSON.stringify(sql)}, params)
db.commit()
db.close()
`;
  execFileSync("python3", ["-c", script, JSON.stringify(params)], { encoding: "utf8" });
}

router.get("/guilds/:guildId/stats", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const { guildId } = req.params;
    const total_users = queryDbOne("SELECT COUNT(*) as c FROM users WHERE guild_id = ?", [guildId])?.c ?? 0;
    const total_messages = queryDbOne("SELECT SUM(messages) as s FROM users WHERE guild_id = ?", [guildId])?.s ?? 0;
    const top_level = queryDbOne("SELECT MAX(level) as m FROM users WHERE guild_id = ?", [guildId])?.m ?? 0;
    const mod_actions = queryDbOne("SELECT COUNT(*) as c FROM mod_logs WHERE guild_id = ?", [guildId])?.c ?? 0;
    res.json({ total_users, total_messages, top_level, mod_actions });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

router.get("/guilds/:guildId/ranking", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const rows = queryDb(
      "SELECT user_id, username, level, xp, messages FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 20",
      [req.params.guildId]
    );
    res.json(rows);
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

router.get("/guilds/:guildId/users", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const rows = queryDb(
      "SELECT user_id, username, xp, level, messages FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC",
      [req.params.guildId]
    );
    res.json(rows);
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

router.get("/guilds/:guildId/modlogs", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const page = Math.max(1, parseInt(String(req.query["page"] || "1")));
    const perPage = 20;
    const offset = (page - 1) * perPage;
    const { guildId } = req.params;
    const total = queryDbOne("SELECT COUNT(*) as c FROM mod_logs WHERE guild_id = ?", [guildId])?.c ?? 0;
    const logs = queryDb(
      "SELECT action, moderator_name, target_name, reason, timestamp FROM mod_logs WHERE guild_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
      [guildId, perPage, offset]
    );
    res.json({
      total, page,
      logs: logs.map((l: any) => ({
        action: l.action, moderator: l.moderator_name,
        target: l.target_name, reason: l.reason, timestamp: l.timestamp,
      })),
    });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

router.get("/guilds/:guildId/settings", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const row = queryDbOne(
      "SELECT prefix, welcome_channel, welcome_message, log_channel, xp_enabled, mod_role FROM guild_settings WHERE guild_id = ?",
      [req.params.guildId]
    );
    res.json(row || { prefix: "n!", welcome_channel: "", welcome_message: "", log_channel: "", xp_enabled: 1, mod_role: "" });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

router.post("/guilds/:guildId/settings", (req, res) => {
  if (!requireSecret(req, res)) return;
  try {
    const { guildId } = req.params;
    const allowed = ["prefix", "welcome_channel", "welcome_message", "log_channel", "xp_enabled", "mod_role"];
    execDb("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", [guildId]);
    for (const key of allowed) {
      if (key in req.body) {
        execDb(`UPDATE guild_settings SET ${key} = ? WHERE guild_id = ?`, [req.body[key], guildId]);
      }
    }
    res.json({ success: true });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

export default router;
