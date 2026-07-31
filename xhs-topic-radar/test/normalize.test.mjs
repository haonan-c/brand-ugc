import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { extractCommentTexts, extractItems, extractSuggestionTerms, normalizeNote, parseCount } from "../lib/normalize.mjs";

const fixture = async (name) => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), "utf8"));

test("normalizes a flat legacy search envelope and preserves exact URLs", async () => {
  const response = await fixture("search.json");
  const items = extractItems(response);
  assert.equal(items.length, 2);
  const note = normalizeNote(items[0], { audience: "student", keyword: "大学生软著" });
  assert.equal(note.noteId, "note-1");
  assert.equal(note.noteUrl, "https://www.xiaohongshu.com/explore/note-1?xsec_token=abc");
  assert.equal(note.likes, 12_000);
  assert.equal(note.collects, 830);
  assert.equal(note.audience, "student");
  assert.ok(note.preliminaryScore > 0);
});

test("extracts comments and parses human counts", async () => {
  const response = await fixture("comments.json");
  assert.deepEqual(extractCommentTexts(response), ["我们学校的综测文件在哪里查？", "大三现在申请还来得及吗？"]);
  assert.equal(parseCount("2.5万"), 25_000);
  assert.equal(parseCount("1.2k"), 1_200);
});

test("normalizes nested TikHub search and comment responses", async () => {
  const search = await fixture("tikhub-search.json");
  const items = extractItems(search);
  assert.equal(items.length, 1);
  const note = normalizeNote(items[0], { audience: "student", keyword: "大学生软著" });
  assert.equal(note.noteId, "note-tikhub-1");
  assert.equal(note.likes, 11_000);
  assert.equal(note.comments, 30);
  assert.equal(note.noteUrlOrigin, "tikhub_note_id_xsec_token");
  assert.equal(note.noteUrl, "https://www.xiaohongshu.com/explore/note-tikhub-1?xsec_token=token-value=&xsec_source=pc_search");

  const comments = await fixture("tikhub-comments.json");
  assert.deepEqual(extractCommentTexts(comments), ["学校的创新学分文件在哪里查看？", "申请需要准备什么材料？"]);

  const suggestions = await fixture("tikhub-suggest.json");
  assert.deepEqual(extractSuggestionTerms(suggestions), ["软著申请流程", "软著代理"]);
});
