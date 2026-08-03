import { randomUUID } from "node:crypto";
import {
	chmod,
	mkdir,
	readFile,
	rename,
	rm,
	writeFile,
} from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";

const CREDENTIAL_DIRECTORY = "pi-xhs-topic-radar";
const CREDENTIAL_FILENAME = "credentials.json";
const PROJECT_CREDENTIAL_PATH = join(".brand_ugc", "credentials.json");

export function validateTikHubApiKey(value) {
	const apiKey = String(value ?? "").trim();
	if (apiKey.length < 16) {
		throw new Error("TikHub API Key 长度不正确，请检查后重新输入。");
	}
	if (/\s/.test(apiKey)) {
		throw new Error("TikHub API Key 中不能包含空格或换行。");
	}
	return apiKey;
}

export function maskTikHubApiKey(apiKey) {
	const normalized = validateTikHubApiKey(apiKey);
	return `••••••••${normalized.slice(-4)}`;
}

export function getCredentialPaths({ configHome } = {}) {
	const root = resolve(
		configHome ?? process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config"),
	);
	const directory = join(root, CREDENTIAL_DIRECTORY);
	return {
		directory,
		file: join(directory, CREDENTIAL_FILENAME),
	};
}

export function getProjectCredentialPath(projectRoot) {
	return projectRoot ? join(resolve(projectRoot), PROJECT_CREDENTIAL_PATH) : null;
}

async function readCredentialFile(file) {
	try {
		const parsed = JSON.parse(await readFile(file, "utf8"));
		if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
			throw new Error(`凭证文件顶层必须是 JSON 对象：${file}`);
		}
		return parsed;
	} catch (error) {
		if (error?.code === "ENOENT") return null;
		if (error instanceof SyntaxError) {
			throw new Error(`凭证文件格式损坏：${file}`);
		}
		throw error;
	}
}

async function writeCredentialFile(file, payload) {
	const directory = dirname(file);
	await mkdir(directory, { recursive: true, mode: 0o700 });
	await chmod(directory, 0o700);
	const temporaryFile = join(
		directory,
		`.${CREDENTIAL_FILENAME}.${process.pid}.${randomUUID()}.tmp`,
	);
	try {
		await writeFile(
			temporaryFile,
			`${JSON.stringify(payload, null, 2)}\n`,
			{ encoding: "utf8", mode: 0o600, flag: "wx" },
		);
		await chmod(temporaryFile, 0o600);
		await rename(temporaryFile, file);
		await chmod(file, 0o600);
	} finally {
		await rm(temporaryFile, { force: true }).catch(() => {});
	}
}

export async function loadTikHubCredential({
	env = process.env,
	configHome,
	projectRoot,
} = {}) {
	const environmentKey = String(env.TIKHUB_API_KEY ?? "").trim();
	if (environmentKey) {
		const apiKey = validateTikHubApiKey(environmentKey);
		return {
			apiKey,
			masked: maskTikHubApiKey(apiKey),
			source: "environment",
			path: null,
		};
	}

	const projectFile = getProjectCredentialPath(projectRoot);
	if (projectFile) {
		const projectCredentials = await readCredentialFile(projectFile);
		const projectKey = String(projectCredentials?.tikhubApiKey ?? "").trim();
		if (projectKey) {
			const apiKey = validateTikHubApiKey(projectKey);
			return {
				apiKey,
				masked: maskTikHubApiKey(apiKey),
				source: "project-file",
				path: projectFile,
			};
		}
	}

	const { file } = getCredentialPaths({ configHome });
	const parsed = await readCredentialFile(file);
	if (!parsed) return null;
	const apiKey = validateTikHubApiKey(parsed?.tikhubApiKey);
	return {
		apiKey,
		masked: maskTikHubApiKey(apiKey),
		source: "local-file",
		path: file,
	};
}

export async function saveTikHubCredential(apiKey, { configHome, projectRoot } = {}) {
	const normalized = validateTikHubApiKey(apiKey);
	const projectFile = getProjectCredentialPath(projectRoot);
	if (projectFile) {
		const existing = (await readCredentialFile(projectFile)) ?? {
			schemaVersion: 1,
			tikhubApiKey: "",
			evolinkApiKey: "",
		};
		await writeCredentialFile(projectFile, {
			...existing,
			schemaVersion: existing.schemaVersion ?? 1,
			tikhubApiKey: normalized,
		});
		return {
			apiKey: normalized,
			masked: maskTikHubApiKey(normalized),
			source: "project-file",
			path: projectFile,
		};
	}
	const { file } = getCredentialPaths({ configHome });
	await writeCredentialFile(file, { version: 1, tikhubApiKey: normalized });
	return {
		apiKey: normalized,
		masked: maskTikHubApiKey(normalized),
		source: "local-file",
		path: file,
	};
}

export async function clearTikHubCredential({ configHome, projectRoot } = {}) {
	const projectFile = getProjectCredentialPath(projectRoot);
	if (projectFile) {
		const existing = await readCredentialFile(projectFile);
		if (existing) {
			await writeCredentialFile(projectFile, {
				...existing,
				tikhubApiKey: "",
			});
		}
		return projectFile;
	}
	const { file } = getCredentialPaths({ configHome });
	await rm(file, { force: true });
	return file;
}
