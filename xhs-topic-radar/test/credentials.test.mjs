import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
	clearTikHubCredential,
	getCredentialPaths,
	getProjectCredentialPath,
	loadTikHubCredential,
	maskTikHubApiKey,
	saveTikHubCredential,
	validateTikHubApiKey,
} from "../lib/credentials.mjs";

const TEST_KEY = "test_tikhub_key_1234567890";

test("validates and masks TikHub keys without exposing the full value", () => {
	assert.equal(validateTikHubApiKey(`  ${TEST_KEY}  `), TEST_KEY);
	assert.equal(maskTikHubApiKey(TEST_KEY), "••••••••7890");
	assert.throws(() => validateTikHubApiKey("short"), /长度/);
	assert.throws(() => validateTikHubApiKey("test key with spaces"), /空格/);
});

test("stores Web-entered credentials locally with restrictive permissions", async () => {
	const configHome = await mkdtemp(join(tmpdir(), "topic-radar-credentials-"));
	try {
		const saved = await saveTikHubCredential(TEST_KEY, { configHome });
		assert.equal(saved.masked, "••••••••7890");
		assert.equal((await stat(saved.path)).mode & 0o777, 0o600);
		assert.equal(
			(await stat(getCredentialPaths({ configHome }).directory)).mode & 0o777,
			0o700,
		);
		const raw = await readFile(saved.path, "utf8");
		assert.equal(JSON.parse(raw).tikhubApiKey, TEST_KEY);

		const loaded = await loadTikHubCredential({ env: {}, configHome });
		assert.deepEqual(loaded, saved);
		await clearTikHubCredential({ configHome });
		assert.equal(await loadTikHubCredential({ env: {}, configHome }), null);
	} finally {
		await rm(configHome, { recursive: true, force: true });
	}
});

test("environment credentials take precedence over the local Web credential", async () => {
	const configHome = await mkdtemp(join(tmpdir(), "topic-radar-credentials-"));
	try {
		await saveTikHubCredential(TEST_KEY, { configHome });
		const environmentKey = "environment_key_1234567890";
		const loaded = await loadTikHubCredential({
			env: { TIKHUB_API_KEY: environmentKey },
			configHome,
		});
		assert.equal(loaded.apiKey, environmentKey);
		assert.equal(loaded.source, "environment");
		assert.equal(loaded.path, null);
	} finally {
		await rm(configHome, { recursive: true, force: true });
	}
});

test("project credentials take precedence over the user-level credential", async () => {
	const root = await mkdtemp(join(tmpdir(), "topic-radar-project-credentials-"));
	const configHome = await mkdtemp(join(tmpdir(), "topic-radar-credentials-"));
	try {
		await saveTikHubCredential("user_level_key_1234567890", { configHome });
		const saved = await saveTikHubCredential(TEST_KEY, { projectRoot: root });
		assert.equal(saved.source, "project-file");
		assert.equal(saved.path, getProjectCredentialPath(root));
		assert.equal((await stat(saved.path)).mode & 0o777, 0o600);

		const loaded = await loadTikHubCredential({
			env: {},
			projectRoot: root,
			configHome,
		});
		assert.equal(loaded.apiKey, TEST_KEY);
		assert.equal(loaded.source, "project-file");

		await clearTikHubCredential({ projectRoot: root });
		const cleared = JSON.parse(await readFile(saved.path, "utf8"));
		assert.equal(cleared.tikhubApiKey, "");
	} finally {
		await rm(root, { recursive: true, force: true });
		await rm(configHome, { recursive: true, force: true });
	}
});
