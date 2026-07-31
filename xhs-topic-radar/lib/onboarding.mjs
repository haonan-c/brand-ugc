import { mkdir, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

const SOFTWARE_COPYRIGHT_PATTERN = /软著|软件著作权/;

export function hasWorkspaceConfig(workspace) {
  return existsSync(join(workspace, "config", "topic-radar.json"));
}

export function buildWorkspaceConfig(defaultConfig, industryInput, lookbackDays) {
  const industry = String(industryInput ?? "").trim();
  if (industry.length < 2) throw new Error("行业名称至少需要 2 个字符");
  if (!Number.isInteger(lookbackDays) || lookbackDays < 1 || lookbackDays > 180) {
    throw new Error("时间周期必须是 1–180 天的整数");
  }

  const config = structuredClone(defaultConfig);
  config.industry = industry;
  config.lookbackDays = lookbackDays;
  config.onboarding = {
    completed: true,
    configuredAt: new Date().toISOString(),
  };

  if (SOFTWARE_COPYRIGHT_PATTERN.test(industry)) return config;

  config.audienceLabels = { general: `${industry}目标用户` };
  config.audienceQuotas = { general: config.outputCount };
  config.collection.suggestionSeeds = [
    { audience: "general", keyword: industry },
    { audience: "general", keyword: `${industry} 价格` },
    { audience: "general", keyword: `${industry} 避坑` },
  ];
  config.queries = [
    industry,
    `${industry} 攻略`,
    `${industry} 避坑`,
    `${industry} 价格`,
    `${industry} 流程`,
    `${industry} 怎么选`,
    `${industry} 常见问题`,
    `${industry} 真实体验`,
    `${industry} 最新政策`,
  ].map((keyword) => ({ audience: "general", keyword }));
  return config;
}

export async function saveWorkspaceConfig(workspace, config) {
  const path = join(workspace, "config", "topic-radar.json");
  await mkdir(dirname(path), { recursive: true });
  const temporaryPath = `${path}.tmp-${process.pid}`;
  await writeFile(temporaryPath, `${JSON.stringify(config, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporaryPath, path);
  return path;
}

export function describeSetup(config) {
  const labels = Object.entries(config.audienceQuotas)
    .map(([id, quota]) => `${config.audienceLabels?.[id] ?? id} ${quota} 条`)
    .join("、");
  const plannedRequests = config.collection.suggestionSeeds.length
    + config.queries.length * config.collection.pagesPerQuery
    + config.collection.maxCommentNotes;
  return {
    industry: config.industry,
    lookbackDays: config.lookbackDays,
    audiences: labels,
    suggestionSeeds: config.collection.suggestionSeeds.map((item) => item.keyword),
    queryKeywords: config.queries.map((item) => item.keyword),
    plannedRequests,
    maxCostUsd: config.tikhub.maxEstimatedCostUsd,
  };
}
