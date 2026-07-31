import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { createConfigSignature } from "./config.mjs";
import { extractSuggestionTerms } from "./normalize.mjs";
import {
	getRunPricing,
	getTikHubUserInfo,
	roundMoney,
	runTikHub,
	TIKHUB_ENDPOINTS,
} from "./tikhub.mjs";

/**
 * @param {{ workspace?: string, config?: any, apiKey?: string, signal?: AbortSignal, onProgress?: (message: string) => void }} [options]
 */
export async function discoverSearchSuggestions({
	workspace = process.cwd(),
	config,
	apiKey = process.env.TIKHUB_API_KEY,
	signal,
	onProgress,
} = {}) {
	workspace = resolve(workspace);
	if (!apiKey) throw new Error("TIKHUB_API_KEY is not configured");
	if (!config)
		throw new Error("Topic radar config is required for demand discovery");

	onProgress?.("正在通过 TikHub 官方定价接口执行费用预检");
	const pricing = await getRunPricing(config, { signal, apiKey });
	validateFullRunPricing(pricing, config);
	const user = await getTikHubUserInfo({
		apiKey,
		baseUrl: config.tikhub.baseUrl,
		timeoutMs: config.collection.commandTimeoutMs,
		signal,
	});
	const available = Number(user.balance ?? 0) + Number(user.free_credit ?? 0);
	if (Number.isFinite(available) && available < pricing.totalPrice) {
		throw new Error(
			`TikHub balance is insufficient for the full bounded run: US$${available.toFixed(4)} < US$${pricing.totalPrice.toFixed(4)}`,
		);
	}

	const startedAt = new Date().toISOString();
	const runDate = localDate();
	const planId = `${runDate}-${startedAt.replace(/\D/g, "").slice(8, 14)}-demand`;
	const rawDir = join(workspace, "data", "raw", runDate);
	const planDir = join(workspace, "data", "plans");
	await Promise.all([
		mkdir(rawDir, { recursive: true }),
		mkdir(planDir, { recursive: true }),
	]);

	const searchSuggestions = [];
	const errors = [];
	let requestCount = 0;
	let estimatedCostUsd = 0;
	let nextRequestAt = 0;

	for (
		let index = 0;
		index < config.collection.suggestionSeeds.length;
		index++
	) {
		const seed = config.collection.suggestionSeeds[index];
		onProgress?.(
			`[需求词 ${index + 1}/${config.collection.suggestionSeeds.length}] ${seed.keyword}`,
		);
		const waitMs = Math.max(0, nextRequestAt - Date.now());
		if (waitMs > 0) await delay(waitMs, signal);
		nextRequestAt = Date.now() + config.collection.minRequestIntervalMs;
		requestCount++;
		estimatedCostUsd = roundMoney(
			estimatedCostUsd + pricing.suggestions.basePrice,
		);
		try {
			const response = await runTikHub(
				TIKHUB_ENDPOINTS.searchSuggest,
				{ keyword: seed.keyword },
				{
					apiKey,
					baseUrl: config.tikhub.baseUrl,
					timeoutMs: config.collection.commandTimeoutMs,
					signal,
				},
			);
			await writeFile(
				join(
					rawDir,
					`suggest-${planId}-${String(index + 1).padStart(2, "0")}-${safeName(seed.keyword)}.json`,
				),
				JSON.stringify(response, null, 2),
			);
			searchSuggestions.push({
				audience: seed.audience,
				seed: seed.keyword,
				terms: extractSuggestionTerms(
					response,
					config.collection.maxSuggestionsPerSeed,
				),
			});
		} catch (error) {
			searchSuggestions.push({
				audience: seed.audience,
				seed: seed.keyword,
				terms: [],
			});
			errors.push({
				stage: `suggest:${seed.keyword}`,
				message: cleanError(error),
			});
		}
	}

	const plan = {
		version: 1,
		planId,
		runDate,
		startedAt,
		completedAt: new Date().toISOString(),
		configSignature: createConfigSignature(config),
		industry: config.industry,
		lookbackDays: config.lookbackDays,
		pricing,
		requestCount,
		estimatedCostUsd,
		searchSuggestions,
		errors,
	};
	const planPath = join(planDir, `${planId}.json`);
	await writeFile(planPath, `${JSON.stringify(plan, null, 2)}\n`, "utf8");
	return { ...plan, planPath };
}

function validateFullRunPricing(pricing, config) {
	if (pricing.currency !== "USD")
		throw new Error(`Unsupported TikHub pricing currency: ${pricing.currency}`);
	if (pricing.requestCount > config.tikhub.maxRequestsPerRun) {
		throw new Error(
			`Planned requests exceed hard cap: ${pricing.requestCount} > ${config.tikhub.maxRequestsPerRun}`,
		);
	}
	if (pricing.totalPrice > config.tikhub.maxEstimatedCostUsd) {
		throw new Error(
			`Official TikHub estimate exceeds hard cap: US$${pricing.totalPrice} > US$${config.tikhub.maxEstimatedCostUsd}`,
		);
	}
}

function delay(milliseconds, signal) {
	return new Promise((resolvePromise, reject) => {
		const timer = setTimeout(done, milliseconds);
		const abort = () => {
			clearTimeout(timer);
			signal?.removeEventListener("abort", abort);
			reject(new Error("Demand discovery aborted"));
		};
		function done() {
			signal?.removeEventListener("abort", abort);
			resolvePromise();
		}
		if (signal?.aborted) abort();
		else signal?.addEventListener("abort", abort, { once: true });
	});
}

function safeName(value) {
	return (
		String(value)
			.replace(/[^\p{L}\p{N}._-]+/gu, "-")
			.replace(/^-+|-+$/g, "")
			.slice(0, 60) || "item"
	);
}

function cleanError(error) {
	return String(error?.message ?? error)
		.replace(/TIKHUB_API_KEY=[^\s]+/g, "TIKHUB_API_KEY=[REDACTED]")
		.replace(/Bearer\s+[A-Za-z0-9+/=_-]+/gi, "Bearer [REDACTED]")
		.slice(0, 1000);
}

function localDate(date = new Date()) {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const day = String(date.getDate()).padStart(2, "0");
	return `${year}-${month}-${day}`;
}
