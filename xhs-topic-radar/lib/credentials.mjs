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
import { join, resolve } from "node:path";

const CREDENTIAL_DIRECTORY = "pi-xhs-topic-radar";
const CREDENTIAL_FILENAME = "credentials.json";

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

export async function loadTikHubCredential({
	env = process.env,
	configHome,
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

	const { file } = getCredentialPaths({ configHome });
	let parsed;
	try {
		parsed = JSON.parse(await readFile(file, "utf8"));
	} catch (error) {
		if (error?.code === "ENOENT") return null;
		if (error instanceof SyntaxError) {
			throw new Error(`TikHub 凭据文件格式损坏：${file}`);
		}
		throw error;
	}
	const apiKey = validateTikHubApiKey(parsed?.tikhubApiKey);
	return {
		apiKey,
		masked: maskTikHubApiKey(apiKey),
		source: "local-file",
		path: file,
	};
}

export async function saveTikHubCredential(apiKey, { configHome } = {}) {
	const normalized = validateTikHubApiKey(apiKey);
	const { directory, file } = getCredentialPaths({ configHome });
	await mkdir(directory, { recursive: true, mode: 0o700 });
	await chmod(directory, 0o700);
	const temporaryFile = join(
		directory,
		`.${CREDENTIAL_FILENAME}.${process.pid}.${randomUUID()}.tmp`,
	);
	try {
		await writeFile(
			temporaryFile,
			`${JSON.stringify({ version: 1, tikhubApiKey: normalized }, null, 2)}\n`,
			{ encoding: "utf8", mode: 0o600, flag: "wx" },
		);
		await chmod(temporaryFile, 0o600);
		await rename(temporaryFile, file);
		await chmod(file, 0o600);
	} finally {
		await rm(temporaryFile, { force: true }).catch(() => {});
	}
	return {
		apiKey: normalized,
		masked: maskTikHubApiKey(normalized),
		source: "local-file",
		path: file,
	};
}

export async function clearTikHubCredential({ configHome } = {}) {
	const { file } = getCredentialPaths({ configHome });
	await rm(file, { force: true });
	return file;
}
