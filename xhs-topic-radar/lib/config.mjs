import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function getPackageRoot() {
  return PACKAGE_ROOT;
}

export function resolveWorkspace(cwd = process.cwd()) {
  return resolve(cwd);
}

export function createConfigSignature(config) {
  const material = {
    reportSchemaVersion: 3,
    industry: config.industry,
    lookbackDays: config.lookbackDays,
    outputCount: config.outputCount,
    audienceQuotas: config.audienceQuotas,
    queries: config.queries,
    suggestionSeeds: config.collection.suggestionSeeds,
    maxEvidenceItems: config.collection.maxEvidenceItems,
  };
  return createHash("sha256").update(JSON.stringify(material)).digest("hex").slice(0, 20);
}

export async function loadConfig(workspace = process.cwd()) {
  const localPath = join(workspace, "config", "topic-radar.json");
  const defaultPath = join(PACKAGE_ROOT, "config", "default-topic-radar.json");
  const path = existsSync(localPath) ? localPath : defaultPath;
  return readValidatedConfig(path);
}

export async function loadDefaultConfig() {
  return readValidatedConfig(join(PACKAGE_ROOT, "config", "default-topic-radar.json"));
}

async function readValidatedConfig(path) {
  const config = JSON.parse(await readFile(path, "utf8"));
  validateConfig(config);
  return { config, path };
}

function validateConfig(config) {
  if (config.platform !== "xhs") throw new Error("MVP only supports platform=xhs");
  if (config.provider !== "tikhub") throw new Error("MVP data provider must be tikhub");
  if (typeof config.industry !== "string" || config.industry.trim().length < 2) {
    throw new Error("industry must contain at least 2 characters");
  }
  if (!Number.isInteger(config.lookbackDays) || config.lookbackDays < 1 || config.lookbackDays > 180) {
    throw new Error("lookbackDays must be an integer from 1 to 180");
  }
  if (!Number.isInteger(config.outputCount) || config.outputCount < 1) {
    throw new Error("outputCount must be a positive integer");
  }
  const quotaTotal = Object.values(config.audienceQuotas ?? {}).reduce((sum, value) => sum + Number(value), 0);
  if (quotaTotal !== config.outputCount) {
    throw new Error(`audienceQuotas total (${quotaTotal}) must equal outputCount (${config.outputCount})`);
  }
  for (const audience of Object.keys(config.audienceQuotas ?? {})) {
    if (!config.audienceLabels?.[audience]) throw new Error(`audienceLabels is missing ${audience}`);
  }
  if (!Array.isArray(config.queries) || config.queries.length === 0) {
    throw new Error("queries must not be empty");
  }
  if (config.collection.pagesPerQuery !== 1) {
    throw new Error("TikHub MVP requires collection.pagesPerQuery=1");
  }
  if (!Number.isInteger(config.collection.minRequestIntervalMs) || config.collection.minRequestIntervalMs < 0) {
    throw new Error("collection.minRequestIntervalMs must be a non-negative integer");
  }
  if (!Array.isArray(config.collection.suggestionSeeds) || config.collection.suggestionSeeds.length === 0) {
    throw new Error("collection.suggestionSeeds must not be empty");
  }
  const plannedRequests = config.collection.suggestionSeeds.length
    + config.queries.length * config.collection.pagesPerQuery
    + config.collection.maxCommentNotes;
  if (!Number.isInteger(config.tikhub?.maxRequestsPerRun) || config.tikhub.maxRequestsPerRun < plannedRequests) {
    throw new Error(`tikhub.maxRequestsPerRun must cover the planned ${plannedRequests} requests`);
  }
  if (!Number.isFinite(config.tikhub?.maxEstimatedCostUsd) || config.tikhub.maxEstimatedCostUsd <= 0) {
    throw new Error("tikhub.maxEstimatedCostUsd must be positive");
  }
}
