import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { DatabaseSync } from "node:sqlite";

export function openDatabase(workspace) {
  const path = join(workspace, "data", "topic-radar.sqlite");
  mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;");
  db.exec(`
    CREATE TABLE IF NOT EXISTS runs (
      run_id TEXT PRIMARY KEY,
      run_date TEXT NOT NULL,
      provider TEXT NOT NULL DEFAULT 'tikhub',
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      completed_at TEXT,
      estimated_credits INTEGER NOT NULL DEFAULT 0,
      estimated_cost_usd REAL NOT NULL DEFAULT 0,
      request_count INTEGER NOT NULL DEFAULT 0,
      note_count INTEGER NOT NULL DEFAULT 0,
      error_count INTEGER NOT NULL DEFAULT 0,
      errors_json TEXT NOT NULL DEFAULT '[]',
      pending_path TEXT,
      report_path TEXT
    );

    CREATE TABLE IF NOT EXISTS source_items (
      identity TEXT PRIMARY KEY,
      note_id TEXT,
      note_url TEXT,
      title TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      author TEXT,
      publish_time TEXT,
      audience TEXT NOT NULL,
      matched_keyword TEXT NOT NULL,
      likes INTEGER NOT NULL DEFAULT 0,
      collects INTEGER NOT NULL DEFAULT 0,
      comments INTEGER NOT NULL DEFAULT 0,
      shares INTEGER NOT NULL DEFAULT 0,
      preliminary_score INTEGER NOT NULL DEFAULT 0,
      first_seen TEXT NOT NULL,
      last_seen TEXT NOT NULL,
      raw_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS source_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      identity TEXT NOT NULL,
      captured_at TEXT NOT NULL,
      likes INTEGER NOT NULL DEFAULT 0,
      collects INTEGER NOT NULL DEFAULT 0,
      comments INTEGER NOT NULL DEFAULT 0,
      shares INTEGER NOT NULL DEFAULT 0,
      UNIQUE(run_id, identity),
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );

    CREATE TABLE IF NOT EXISTS topic_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      rank INTEGER NOT NULL,
      audience TEXT NOT NULL,
      title TEXT NOT NULL,
      why_now TEXT NOT NULL,
      user_question TEXT NOT NULL,
      angle TEXT NOT NULL,
      title_alternatives_json TEXT NOT NULL,
      content_format TEXT NOT NULL,
      score INTEGER NOT NULL,
      risk_note TEXT NOT NULL,
      source_urls_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(run_id, rank),
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
  `);
  ensureColumn(db, "runs", "provider", "TEXT NOT NULL DEFAULT 'tikhub'");
  ensureColumn(db, "runs", "estimated_cost_usd", "REAL NOT NULL DEFAULT 0");
  ensureColumn(db, "runs", "request_count", "INTEGER NOT NULL DEFAULT 0");
  return db;
}

export function createRun(db, run) {
  db.prepare(`
    INSERT INTO runs (run_id, run_date, provider, status, started_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(run.runId, run.runDate, run.provider ?? "tikhub", run.status, run.startedAt);
}

export function updateRun(db, runId, patch) {
  const allowed = new Map([
    ["status", "status"], ["completedAt", "completed_at"],
    ["estimatedCredits", "estimated_credits"], ["estimatedCostUsd", "estimated_cost_usd"],
    ["requestCount", "request_count"], ["noteCount", "note_count"],
    ["errorCount", "error_count"], ["errorsJson", "errors_json"],
    ["pendingPath", "pending_path"], ["reportPath", "report_path"],
  ]);
  const entries = Object.entries(patch).filter(([key]) => allowed.has(key));
  if (entries.length === 0) return;
  const assignments = entries.map(([key]) => `${allowed.get(key)} = ?`).join(", ");
  db.prepare(`UPDATE runs SET ${assignments} WHERE run_id = ?`).run(...entries.map(([, value]) => value), runId);
}

export function upsertSourceItem(db, runId, note) {
  db.prepare(`
    INSERT INTO source_items (
      identity, note_id, note_url, title, description, author, publish_time,
      audience, matched_keyword, likes, collects, comments, shares,
      preliminary_score, first_seen, last_seen, raw_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(identity) DO UPDATE SET
      note_id=excluded.note_id,
      note_url=excluded.note_url,
      title=excluded.title,
      description=excluded.description,
      author=excluded.author,
      publish_time=excluded.publish_time,
      audience=excluded.audience,
      matched_keyword=excluded.matched_keyword,
      likes=excluded.likes,
      collects=excluded.collects,
      comments=excluded.comments,
      shares=excluded.shares,
      preliminary_score=excluded.preliminary_score,
      last_seen=excluded.last_seen,
      raw_json=excluded.raw_json
  `).run(
    note.identity, note.noteId, note.noteUrl, note.title, note.description, note.author,
    note.publishTime, note.audience, note.matchedKeyword, note.likes, note.collects,
    note.comments, note.shares, note.preliminaryScore, note.discoveredAt,
    note.discoveredAt, JSON.stringify(note.raw),
  );
  db.prepare(`
    INSERT OR REPLACE INTO source_snapshots
      (run_id, identity, captured_at, likes, collects, comments, shares)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(runId, note.identity, note.discoveredAt, note.likes, note.collects, note.comments, note.shares);
}

export function saveCandidates(db, runId, topics) {
  const insert = db.prepare(`
    INSERT INTO topic_candidates (
      run_id, rank, audience, title, why_now, user_question, angle,
      title_alternatives_json, content_format, score, risk_note,
      source_urls_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  db.exec("BEGIN");
  try {
    db.prepare("DELETE FROM topic_candidates WHERE run_id = ?").run(runId);
    const now = new Date().toISOString();
    topics.forEach((topic, index) => insert.run(
      runId, index + 1, topic.audience, topic.title, topic.whyNow,
      topic.userQuestion, topic.angle, JSON.stringify(topic.titleAlternatives),
      topic.contentFormat, topic.score, topic.riskNote,
      JSON.stringify(topic.sourceUrls), now,
    ));
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

export function getLatestRun(db) {
  return db.prepare("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").get();
}

function ensureColumn(db, table, column, definition) {
  const columns = db.prepare(`PRAGMA table_info(${table})`).all().map((row) => row.name);
  if (!columns.includes(column)) db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
}

export function getRecentTopicTitles(db, days = 90) {
  return db.prepare(`
    SELECT title FROM topic_candidates
    WHERE created_at >= datetime('now', ?)
  `).all(`-${days} days`).map((row) => row.title);
}
