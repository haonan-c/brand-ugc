import { createHash } from "node:crypto";

const AUDIENCE_TERMS = {
  student: ["大学生", "高校", "学校", "加分", "创新学分", "综测", "评奖", "保研", "学生"],
  high_tech_enterprise: ["高企", "高新技术企业", "企业", "知识产权", "研发", "申报", "产品"],
  hangzhou_e_talent: ["杭州", "E类", "人才", "人才认定", "区县", "社保"],
};

export function extractItems(envelope) {
  let data = envelope;
  for (let depth = 0; depth < 5; depth++) {
    if (Array.isArray(data)) return data;
    for (const key of ["items", "notes", "results", "list", "data_list", "comments", "comment_list", "sug_items"]) {
      if (Array.isArray(data?.[key])) return data[key];
    }
    if (data?.data && typeof data.data === "object") data = data.data;
    else break;
  }
  return [];
}

export function normalizeNote(rawInput, query, discoveredAt = new Date().toISOString(), searchRank = null) {
  const raw = rawInput?.note ?? rawInput;
  const noteId = firstString(raw, ["note_id", "noteId", "id", "item_id"]);
  const xsecToken = firstString(raw, ["xsec_token", "xsecToken"]);
  const providedUrl = firstString(raw, ["note_url", "noteUrl", "url", "share_url", "web_url"]);
  const noteUrl = providedUrl || buildXhsNoteUrl(noteId, xsecToken);
  const title = firstString(raw, ["title", "display_title", "note_title", "name"]) || "（无标题）";
  const description = firstString(raw, ["desc", "description", "content", "note_desc", "text"]) || "";
  const author = firstString(raw?.user ?? raw?.author ?? raw, ["nickname", "name", "user_name", "author_name"]);
  const publishTime = normalizeTime(raw.publish_time ?? raw.publishTime ?? raw.timestamp ?? raw.time ?? raw.create_time);
  const likes = firstCount(raw, ["liked_count", "like_count", "likes", "likedCount"]);
  const collects = firstCount(raw, ["collected_count", "collect_count", "collects", "favorite_count"]);
  const comments = firstCount(raw, ["comments_count", "comment_count", "comments", "commentCount"]);
  const shares = firstCount(raw, ["shared_count", "share_count", "shares", "shareCount"]);
  const identity = noteId || noteUrl || hash(`${title}\n${author ?? ""}`);
  const text = `${title}\n${description}`;
  const relevance = scoreRelevance(text, query.audience, query.keyword);
  const engagement = Math.log1p(likes + 2 * collects + 3 * comments + shares) * 8;
  const recency = scoreRecency(publishTime);

  return {
    identity,
    noteId,
    noteUrl,
    noteUrlOrigin: providedUrl ? "provider" : (noteUrl ? "tikhub_note_id_xsec_token" : null),
    title,
    description,
    author,
    publishTime,
    likes,
    collects,
    comments,
    shares,
    audience: query.audience,
    matchedKeyword: query.keyword,
    searchRank: Number.isInteger(searchRank) && searchRank > 0 ? searchRank : null,
    discoveredAt,
    relevance,
    preliminaryScore: Math.min(100, Math.round(relevance * 0.55 + engagement * 0.3 + recency * 0.15)),
    commentTexts: [],
    raw: rawInput,
  };
}

export function extractCommentTexts(envelope) {
  return extractItems(envelope)
    .map((item) => firstString(item, ["content", "text", "comment", "comment_text", "desc"]))
    .filter(Boolean);
}

export function extractSuggestionTerms(envelope, limit = 10) {
  return [...new Set(extractItems(envelope)
    .map((item) => firstString(item, ["text", "keyword", "query", "word"]))
    .filter(Boolean))]
    .slice(0, limit);
}

export function deduplicateNotes(notes) {
  const byIdentity = new Map();
  for (const note of notes) {
    const existing = byIdentity.get(note.identity);
    if (!existing || note.preliminaryScore > existing.preliminaryScore) {
      byIdentity.set(note.identity, note);
    }
  }
  return [...byIdentity.values()];
}

export function selectBalanced(notes, quotas, totalLimit) {
  const selected = [];
  const used = new Set();
  const audiences = Object.keys(quotas);
  for (const audience of audiences) {
    const target = Math.max(1, Math.ceil(totalLimit * quotas[audience] / Object.values(quotas).reduce((a, b) => a + b, 0)));
    for (const note of notes.filter((n) => n.audience === audience).sort(scoreDesc).slice(0, target)) {
      if (!used.has(note.identity)) {
        selected.push(note);
        used.add(note.identity);
      }
    }
  }
  for (const note of [...notes].sort(scoreDesc)) {
    if (selected.length >= totalLimit) break;
    if (!used.has(note.identity)) {
      selected.push(note);
      used.add(note.identity);
    }
  }
  return selected.slice(0, totalLimit);
}

export function toEvidenceItem(note) {
  return {
    identity: note.identity,
    audience: note.audience,
    matchedKeyword: note.matchedKeyword,
    searchRank: note.searchRank,
    title: note.title,
    description: truncate(note.description, 800),
    author: note.author,
    publishTime: note.publishTime,
    metrics: {
      likes: note.likes,
      collects: note.collects,
      comments: note.comments,
      shares: note.shares,
    },
    preliminaryScore: note.preliminaryScore,
    noteUrl: note.noteUrl,
    noteUrlOrigin: note.noteUrlOrigin,
    commentQuestions: note.commentTexts.slice(0, 12).map((text) => truncate(text, 300)),
  };
}

function scoreDesc(a, b) {
  return b.preliminaryScore - a.preliminaryScore;
}

function scoreRelevance(text, audience, matchedKeyword = "") {
  const normalized = text.toLowerCase();
  let score = /软著|软件著作权/.test(normalized) ? 45 : 10;
  const keyword = matchedKeyword.toLowerCase().trim();
  if (keyword && normalized.includes(keyword)) score += 35;
  else {
    for (const term of keyword.split(/\s+/).filter((value) => value.length >= 2)) {
      if (normalized.includes(term)) score += 12;
    }
  }
  for (const term of AUDIENCE_TERMS[audience] ?? []) {
    if (normalized.includes(term.toLowerCase())) score += 7;
  }
  return Math.min(100, score);
}

function scoreRecency(publishTime) {
  if (!publishTime) return 30;
  const ageDays = Math.max(0, (Date.now() - new Date(publishTime).getTime()) / 86_400_000);
  if (ageDays <= 1) return 100;
  if (ageDays <= 3) return 80;
  if (ageDays <= 7) return 60;
  if (ageDays <= 30) return 30;
  return 10;
}

function firstString(object, keys) {
  if (!object || typeof object !== "object") return null;
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number") return String(value);
  }
  return null;
}

function firstCount(object, keys) {
  if (!object || typeof object !== "object") return 0;
  for (const key of keys) {
    if (object[key] !== undefined && object[key] !== null) return parseCount(object[key]);
  }
  const interact = object.interact_info ?? object.interactInfo ?? object.metrics;
  if (interact && interact !== object) return firstCount(interact, keys);
  return 0;
}

export function parseCount(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value ?? "").replace(/,/g, "").trim();
  const number = Number.parseFloat(text);
  if (!Number.isFinite(number)) return 0;
  if (/万/.test(text)) return Math.round(number * 10_000);
  if (/[kK]/.test(text)) return Math.round(number * 1_000);
  if (/[wW]/.test(text)) return Math.round(number * 10_000);
  return Math.round(number);
}

function normalizeTime(value) {
  if (!value) return null;
  if (typeof value === "number") {
    const milliseconds = value < 10_000_000_000 ? value * 1000 : value;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toISOString();
}

function buildXhsNoteUrl(noteId, xsecToken) {
  if (!noteId || !xsecToken) return null;
  return `https://www.xiaohongshu.com/explore/${noteId}?xsec_token=${xsecToken}&xsec_source=pc_search`;
}

function hash(value) {
  return createHash("sha256").update(value).digest("hex").slice(0, 24);
}

function truncate(value, max) {
  return value.length <= max ? value : `${value.slice(0, max)}…`;
}
