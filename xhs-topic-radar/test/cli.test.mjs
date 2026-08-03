import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const CLI = resolve(
  new URL("../scripts/topic_radar.mjs", import.meta.url).pathname,
);

function run(args, { input, env } = {}) {
  return spawnSync(process.execPath, [CLI, ...args], {
    input,
    encoding: "utf8",
    env: { ...process.env, ...env },
  });
}

test("setup stores radar configuration under the shared brand workspace", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "brand-topic-radar-"));
  const result = run([
    "setup",
    "--workspace",
    workspace,
    "--industry",
    "软著",
    "--lookback-days",
    "7",
  ]);
  assert.equal(result.status, 0, result.stderr);
  const body = JSON.parse(result.stdout);
  assert.equal(body.workspace, join(workspace, ".brand_ugc", "topic-radar"));
  assert.equal(body.outputCount, 10);
  assert.deepEqual(body.audienceQuotas, {
    student: 4,
    high_tech_enterprise: 3,
    hangzhou_e_talent: 3,
  });
  const saved = JSON.parse(
    await readFile(
      join(workspace, ".brand_ugc", "topic-radar", "config", "topic-radar.json"),
      "utf8",
    ),
  );
  assert.equal(saved.industry, "软著");
});

test("collect refuses to inspect a plan or spend without explicit approval", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "brand-topic-radar-"));
  const result = run([
    "collect",
    "--workspace",
    workspace,
    "--plan",
    join(workspace, "missing-plan.json"),
  ]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /approval is required/i);
  assert.doesNotMatch(result.stderr, /Cannot read JSON file/);
});

test("key set reads stdin and key status only returns a masked value", async () => {
  const configHome = await mkdtemp(join(tmpdir(), "brand-topic-key-"));
  const env = { XDG_CONFIG_HOME: configHome, TIKHUB_API_KEY: "" };
  const token = "test-token-1234567890";
  const setResult = run(["key", "set"], { input: token, env });
  assert.equal(setResult.status, 0, setResult.stderr);
  assert.doesNotMatch(setResult.stdout, new RegExp(token));
  assert.match(setResult.stdout, /7890/);

  const statusResult = run(["key", "status"], { env });
  assert.equal(statusResult.status, 0, statusResult.stderr);
  assert.doesNotMatch(statusResult.stdout, new RegExp(token));
  const status = JSON.parse(statusResult.stdout);
  assert.equal(status.configured, true);
  assert.equal(status.source, "local-file");
});

test("key commands use project credentials when workspace is provided", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "brand-topic-project-key-"));
  const configHome = await mkdtemp(join(tmpdir(), "brand-topic-user-key-"));
  const env = { XDG_CONFIG_HOME: configHome, TIKHUB_API_KEY: "" };
  const token = "project-token-1234567890";
  const setResult = run(["key", "set", "--workspace", workspace], {
    input: token,
    env,
  });
  assert.equal(setResult.status, 0, setResult.stderr);
  assert.doesNotMatch(setResult.stdout, new RegExp(token));

  const credentials = JSON.parse(
    await readFile(join(workspace, ".brand_ugc", "credentials.json"), "utf8"),
  );
  assert.equal(credentials.tikhubApiKey, token);
  const statusResult = run(["key", "status", "--workspace", workspace], { env });
  const status = JSON.parse(statusResult.stdout);
  assert.equal(status.configured, true);
  assert.equal(status.source, "project-file");
  assert.equal(
    status.configurationPath,
    join(workspace, ".brand_ugc", "credentials.json"),
  );
});

test("missing project key points to the credential file without terminal input", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "brand-topic-missing-key-"));
  const configHome = await mkdtemp(join(tmpdir(), "brand-topic-empty-config-"));
  const env = { XDG_CONFIG_HOME: configHome, TIKHUB_API_KEY: "" };
  const setupResult = run([
    "setup",
    "--workspace",
    workspace,
    "--industry",
    "软著",
    "--lookback-days",
    "7",
  ], { env });
  assert.equal(setupResult.status, 0, setupResult.stderr);

  const result = run(["preview", "--workspace", workspace], { env });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, new RegExp(
    join(workspace, ".brand_ugc", "credentials.json").replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  ));
  assert.match(result.stderr, /tikhubApiKey/);
  assert.doesNotMatch(result.stderr, /key set|interactive terminal|终端输入/i);
});
