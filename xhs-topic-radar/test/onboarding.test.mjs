import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { buildWorkspaceConfig, describeSetup } from "../lib/onboarding.mjs";

const defaults = JSON.parse(await readFile(new URL("../config/default-topic-radar.json", import.meta.url), "utf8"));

test("onboarding preserves the specialized software-copyright template", () => {
  const config = buildWorkspaceConfig(defaults, "软件著作权代理服务", 30);
  assert.equal(config.industry, "软件著作权代理服务");
  assert.equal(config.lookbackDays, 30);
  assert.deepEqual(config.audienceQuotas, { student: 4, high_tech_enterprise: 3, hangzhou_e_talent: 3 });
  assert.equal(config.queries.length, 9);
  assert.equal(describeSetup(config).plannedRequests, 27);
});

test("onboarding creates a safe generic template for another industry", () => {
  const config = buildWorkspaceConfig(defaults, "装修设计", 7);
  assert.equal(config.industry, "装修设计");
  assert.deepEqual(config.audienceQuotas, { general: 10 });
  assert.equal(config.audienceLabels.general, "装修设计目标用户");
  assert.equal(config.collection.suggestionSeeds.length, 3);
  assert.equal(config.queries.length, 9);
  assert.ok(config.queries.every((query) => query.audience === "general"));
  assert.ok(config.queries.some((query) => query.keyword === "装修设计 避坑"));
});
