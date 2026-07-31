import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createConfigSignature } from "../lib/config.mjs";
import { saveWorkspaceConfig } from "../lib/onboarding.mjs";
import { runCollection } from "../lib/pipeline.mjs";

const defaults = JSON.parse(
  await readFile(
    new URL("../config/default-topic-radar.json", import.meta.url),
    "utf8",
  ),
);
const searchFixture = JSON.parse(
  await readFile(new URL("./fixtures/tikhub-search.json", import.meta.url), "utf8"),
);
const commentsFixture = JSON.parse(
  await readFile(new URL("./fixtures/tikhub-comments.json", import.meta.url), "utf8"),
);

function localDate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

test("approved collection persists raw data, SQLite state, comments, and an evidence pack", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "topic-pipeline-"));
  const config = structuredClone(defaults);
  config.lookbackDays = 30;
  config.collection.minRequestIntervalMs = 0;
  config.collection.maxCommentNotes = 1;
  await saveWorkspaceConfig(workspace, config);

  const runDate = localDate();
  const completedAt = new Date().toISOString();
  const pricing = {
    suggestions: {
      endpoint: "/api/v1/xiaohongshu/web_v3/fetch_search_suggest",
      requestCount: 3,
      basePrice: 0.01,
      totalPrice: 0.03,
      currency: "USD",
    },
    search: {
      endpoint: "/api/v1/xiaohongshu/app_v2/search_notes",
      requestCount: config.queries.length,
      basePrice: 0.01,
      totalPrice: config.queries.length * 0.01,
      currency: "USD",
    },
    comments: {
      endpoint: "/api/v1/xiaohongshu/app_v2/get_note_comments",
      requestCount: 1,
      basePrice: 0.01,
      totalPrice: 0.01,
      currency: "USD",
    },
    requestCount: 3 + config.queries.length + 1,
    totalPrice: 0.03 + config.queries.length * 0.01 + 0.01,
    currency: "USD",
  };
  const plan = {
    version: 1,
    runDate,
    completedAt,
    configSignature: createConfigSignature(config),
    pricing,
    requestCount: 3,
    estimatedCostUsd: 0.03,
    searchSuggestions: config.collection.suggestionSeeds.map((seed) => ({
      audience: seed.audience,
      seed: seed.keyword,
      terms: [`${seed.keyword}需求词`],
    })),
    errors: [],
  };

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    assert.equal(init?.headers?.Authorization, "Bearer test-token-1234567890");
    const url = new URL(String(input));
    if (url.pathname.endsWith("/search_notes")) return Response.json(searchFixture);
    if (url.pathname.endsWith("/get_note_comments")) {
      return Response.json(commentsFixture);
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    const result = await runCollection({
      workspace,
      force: true,
      suggestionPlan: plan,
      apiKey: "test-token-1234567890",
    });
    assert.equal(result.cached, false);
    assert.equal(result.requestCount, pricing.requestCount);
    const pending = JSON.parse(await readFile(result.pendingPath, "utf8"));
    assert.equal(pending.version, 3);
    assert.equal(pending.stats.commentNotes, 1);
    assert.equal(pending.evidence.length, 1);
    assert.deepEqual(pending.evidence[0].commentQuestions, [
      "学校的创新学分文件在哪里查看？",
      "申请需要准备什么材料？",
    ]);
    assert.equal(
      pending.evidence[0].noteUrl,
      "https://www.xiaohongshu.com/explore/note-tikhub-1?xsec_token=token-value=&xsec_source=pc_search",
    );
    assert.equal(pending.requestCount, pricing.requestCount);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
