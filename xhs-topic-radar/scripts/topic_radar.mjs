#!/usr/bin/env node
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { loadConfig, loadDefaultConfig } from "../lib/config.mjs";
import {
  clearTikHubCredential,
  loadTikHubCredential,
  saveTikHubCredential,
} from "../lib/credentials.mjs";
import { getLatestRun, openDatabase } from "../lib/database.mjs";
import { discoverSearchSuggestions } from "../lib/discovery.mjs";
import {
  findCachedReport,
  runCollection,
} from "../lib/pipeline.mjs";
import {
  buildWorkspaceConfig,
  hasWorkspaceConfig,
  saveWorkspaceConfig,
} from "../lib/onboarding.mjs";
import { finalizeReport } from "../lib/report.mjs";
import { readHiddenLine } from "../lib/hidden-input.mjs";

const HELP = `xhs-topic-radar

Commands:
  setup    --workspace <brand-workspace> --industry <name> --lookback-days <1-180>
  config   --workspace <brand-workspace>
  key set|status|clear  (key set prompts securely in an interactive terminal)
  preview  --workspace <brand-workspace> [--force]
  collect  --workspace <brand-workspace> --plan <plan.json> --approve [--force]
  finalize --workspace <brand-workspace> --run-id <id> --topics-file <topics.json>
  status   --workspace <brand-workspace>
  report   --workspace <brand-workspace> [--date YYYY-MM-DD]

The brand workspace stores radar state under .brand_ugc/topic-radar/.
JSON results are written to stdout; progress and errors are written to stderr.`;

function parseArgs(values) {
  const options = { _: [] };
  for (let index = 0; index < values.length; index++) {
    const value = values[index];
    if (!value.startsWith("--")) {
      options._.push(value);
      continue;
    }
    const name = value.slice(2);
    if (["approve", "force", "help"].includes(name)) {
      options[name] = true;
      continue;
    }
    const next = values[index + 1];
    if (!next || next.startsWith("--")) {
      throw new Error(`Missing value for --${name}`);
    }
    options[name] = next;
    index++;
  }
  return options;
}

function brandWorkspace(options) {
  return resolve(options.workspace ?? process.cwd());
}

function radarWorkspace(options) {
  return join(brandWorkspace(options), ".brand_ugc", "topic-radar");
}

function required(options, name) {
  const value = options[name];
  if (value === undefined || value === "") throw new Error(`--${name} is required`);
  return value;
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(resolve(path), "utf8"));
  } catch (error) {
    throw new Error(`Cannot read JSON file ${path}: ${error.message}`);
  }
}

async function readStdin() {
  let value = "";
  for await (const chunk of process.stdin) value += chunk;
  return value.trim();
}

function progress(message) {
  process.stderr.write(`[xhs-topic-radar] ${message}\n`);
}

function output(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function requireSetup(workspace) {
  if (!hasWorkspaceConfig(workspace)) {
    throw new Error(
      "Topic radar setup is required. Run setup with an industry and lookback period first.",
    );
  }
}

async function credential() {
  const value = await loadTikHubCredential();
  if (!value) {
    throw new Error(
      "TikHub API Key is not configured. Use TIKHUB_API_KEY or run 'key set' in an interactive terminal.",
    );
  }
  return value;
}

async function setup(options) {
  const workspace = radarWorkspace(options);
  const industry = required(options, "industry");
  const lookbackDays = Number(required(options, "lookback-days"));
  const { config: defaults } = await loadDefaultConfig();
  const config = buildWorkspaceConfig(defaults, industry, lookbackDays);
  const path = await saveWorkspaceConfig(workspace, config);
  output({
    ok: true,
    command: "setup",
    brandWorkspace: brandWorkspace(options),
    workspace,
    configPath: path,
    industry: config.industry,
    lookbackDays: config.lookbackDays,
    outputCount: config.outputCount,
    audienceLabels: config.audienceLabels,
    audienceQuotas: config.audienceQuotas,
    suggestionSeeds: config.collection.suggestionSeeds,
    queries: config.queries,
    requestCap: config.tikhub.maxRequestsPerRun,
    costCapUsd: config.tikhub.maxEstimatedCostUsd,
  });
}

async function showConfig(options) {
  const workspace = radarWorkspace(options);
  requireSetup(workspace);
  const { config, path } = await loadConfig(workspace);
  output({ ok: true, command: "config", workspace, configPath: path, config });
}

async function keyCommand(options) {
  const action = options._[0] ?? "status";
  if (action === "set") {
    const value = process.stdin.isTTY
      ? await readHiddenLine({ prompt: "TikHub API Key（输入内容不会显示）: " })
      : await readStdin();
    const saved = await saveTikHubCredential(value);
    output({
      ok: true,
      command: "key set",
      configured: true,
      masked: saved.masked,
      source: saved.source,
      path: saved.path,
    });
    return;
  }
  if (action === "status") {
    const value = await loadTikHubCredential();
    output({
      ok: true,
      command: "key status",
      configured: Boolean(value),
      masked: value?.masked ?? null,
      source: value?.source ?? null,
      path: value?.path ?? null,
    });
    return;
  }
  if (action === "clear") {
    const path = await clearTikHubCredential();
    const remaining = await loadTikHubCredential();
    output({
      ok: true,
      command: "key clear",
      removedPath: path,
      configured: Boolean(remaining),
      remainingSource: remaining?.source ?? null,
      masked: remaining?.masked ?? null,
    });
    return;
  }
  throw new Error("key command must be set, status, or clear");
}

async function preview(options) {
  const workspace = radarWorkspace(options);
  requireSetup(workspace);
  const { config } = await loadConfig(workspace);
  if (!options.force) {
    const reportPath = await findCachedReport(workspace, config);
    if (reportPath) {
      output({
        ok: true,
        command: "preview",
        cached: true,
        workspace,
        reportPath,
        message: "A matching report already exists today. Use --force to create a paid refresh.",
      });
      return;
    }
  }
  const auth = await credential();
  const plan = await discoverSearchSuggestions({
    workspace,
    config,
    apiKey: auth.apiKey,
    onProgress: progress,
  });
  output({
    ok: true,
    command: "preview",
    cached: false,
    workspace,
    industry: config.industry,
    lookbackDays: config.lookbackDays,
    audienceLabels: config.audienceLabels,
    searchSuggestions: plan.searchSuggestions,
    requestCount: plan.requestCount,
    estimatedCostUsd: plan.estimatedCostUsd,
    remainingRequestCount: plan.pricing.requestCount - plan.requestCount,
    remainingEstimatedCostUsd: Number(
      (plan.pricing.totalPrice - plan.estimatedCostUsd).toFixed(6),
    ),
    totalPlannedRequestCount: plan.pricing.requestCount,
    totalEstimatedCostUsd: plan.pricing.totalPrice,
    planPath: plan.planPath,
    errors: plan.errors,
    requiresApproval: true,
  });
}

async function collect(options) {
  if (!options.approve) {
    throw new Error(
      "Collection approval is required. Review preview terms and costs, then repeat with --approve.",
    );
  }
  const workspace = radarWorkspace(options);
  requireSetup(workspace);
  const planPath = required(options, "plan");
  const plan = await readJson(planPath);
  const auth = await credential();
  const result = await runCollection({
    workspace,
    force: true,
    suggestionPlan: plan,
    apiKey: auth.apiKey,
    onProgress: progress,
  });
  output({
    ok: true,
    command: "collect",
    workspace,
    ...result,
  });
}

async function finalize(options) {
  const workspace = radarWorkspace(options);
  requireSetup(workspace);
  const runId = required(options, "run-id");
  const topicsPath = required(options, "topics-file");
  const parsed = await readJson(topicsPath);
  const topics = Array.isArray(parsed) ? parsed : parsed.topics;
  const result = await finalizeReport({ workspace, runId, topics });
  output({
    ok: true,
    command: "finalize",
    workspace,
    ...result,
  });
}

async function status(options) {
  const workspace = radarWorkspace(options);
  const db = openDatabase(workspace);
  try {
    const latest = getLatestRun(db) ?? null;
    output({ ok: true, command: "status", workspace, latest });
  } finally {
    db.close();
  }
}

async function report(options) {
  const workspace = radarWorkspace(options);
  requireSetup(workspace);
  const { config } = await loadConfig(workspace);
  const filename = options.date ? `${options.date}.md` : config.report.latestFilename;
  const reportPath = join(workspace, config.report.directory, filename);
  output({
    ok: true,
    command: "report",
    workspace,
    exists: existsSync(reportPath),
    reportPath,
  });
}

async function main() {
  const values = process.argv.slice(2);
  const command = values.shift();
  const options = parseArgs(values);
  if (!command || command === "help" || options.help) {
    process.stdout.write(`${HELP}\n`);
    return;
  }
  const commands = {
    setup,
    config: showConfig,
    key: keyCommand,
    preview,
    collect,
    finalize,
    status,
    report,
  };
  const handler = commands[command];
  if (!handler) throw new Error(`Unknown command: ${command}\n\n${HELP}`);
  await handler(options);
}

main().catch((error) => {
  process.stderr.write(
    `${JSON.stringify({ ok: false, error: String(error?.message ?? error) }, null, 2)}\n`,
  );
  process.exitCode = 1;
});
