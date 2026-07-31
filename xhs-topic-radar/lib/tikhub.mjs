const DEFAULT_BASE_URL = "https://api.tikhub.io";

export const TIKHUB_ENDPOINTS = {
	userInfo: "/api/v1/tikhub/user/get_user_info",
	calculatePrice: "/api/v1/tikhub/user/calculate_price",
	searchSuggest: "/api/v1/xiaohongshu/web_v3/fetch_search_suggest",
	searchNotes: "/api/v1/xiaohongshu/app_v2/search_notes",
	noteComments: "/api/v1/xiaohongshu/app_v2/get_note_comments",
};

export async function runTikHub(endpoint, params = {}, options = {}) {
	const apiKey = options.apiKey ?? process.env.TIKHUB_API_KEY;
	if (!apiKey) throw new Error("TIKHUB_API_KEY is not configured");
	const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
	const url = new URL(endpoint, baseUrl);
	for (const [key, value] of Object.entries(params)) {
		if (value !== undefined && value !== null)
			url.searchParams.set(key, String(value));
	}

	const controller = new AbortController();
	const timeout = setTimeout(
		() => controller.abort(),
		options.timeoutMs ?? 90_000,
	);
	const abort = () => controller.abort();
	if (options.signal?.aborted) controller.abort();
	else options.signal?.addEventListener("abort", abort, { once: true });

	try {
		const response = await fetch(url, {
			method: "GET",
			headers: {
				Authorization: `Bearer ${apiKey}`,
				Accept: "application/json",
				"User-Agent": "pi-xhs-topic-radar/0.2.0",
			},
			signal: controller.signal,
		});
		const text = await response.text();
		let body;
		try {
			body = JSON.parse(text);
		} catch {
			throw new Error(`TikHub returned non-JSON response (${response.status})`);
		}
		if (!response.ok || (body?.code !== undefined && body.code !== 200)) {
			const message =
				body?.message_zh || body?.message || `HTTP ${response.status}`;
			throw new Error(`TikHub request failed: ${message}`);
		}
		return body;
	} catch (error) {
		if (error?.name === "AbortError")
			throw new Error("TikHub request timed out or was aborted");
		throw error;
	} finally {
		clearTimeout(timeout);
		options.signal?.removeEventListener("abort", abort);
	}
}

export async function getTikHubUserInfo(options = {}) {
	const response = await runTikHubAdmin(TIKHUB_ENDPOINTS.userInfo, {}, options);
	return response.user_data ?? response.data?.user_data ?? response.data ?? {};
}

export async function calculateTikHubPrice(
	endpoint,
	requestCount,
	options = {},
) {
	const response = await runTikHubAdmin(
		TIKHUB_ENDPOINTS.calculatePrice,
		{
			endpoint,
			request_per_day: requestCount,
		},
		options,
	);
	const data = response.data ?? {};
	const basePrice = Number(data.base_price);
	const totalPrice = Number(data.total_price);
	if (!Number.isFinite(basePrice) || !Number.isFinite(totalPrice)) {
		throw new Error(
			`TikHub pricing response is missing numeric prices for ${endpoint}`,
		);
	}
	return {
		endpoint,
		requestCount,
		basePrice,
		totalPrice,
		currency: data.currency ?? "USD",
	};
}

export async function getRunPricing(config, options = {}) {
	const suggestionRequests = config.collection.suggestionSeeds.length;
	const searchRequests =
		config.queries.length * config.collection.pagesPerQuery;
	const commentRequests = config.collection.maxCommentNotes;
	const common = {
		apiKey: options.apiKey,
		baseUrl: config.tikhub.baseUrl,
		timeoutMs: config.collection.commandTimeoutMs,
		signal: options.signal,
	};
	const suggestions = await calculateTikHubPrice(
		TIKHUB_ENDPOINTS.searchSuggest,
		suggestionRequests,
		common,
	);
	await delay(1_100, options.signal);
	const search = await calculateTikHubPrice(
		TIKHUB_ENDPOINTS.searchNotes,
		searchRequests,
		common,
	);
	await delay(1_100, options.signal);
	const comments = await calculateTikHubPrice(
		TIKHUB_ENDPOINTS.noteComments,
		commentRequests,
		common,
	);
	const currencies = new Set([
		suggestions.currency,
		search.currency,
		comments.currency,
	]);
	if (currencies.size !== 1)
		throw new Error("TikHub returned mixed pricing currencies");
	return {
		suggestions,
		search,
		comments,
		requestCount: suggestionRequests + searchRequests + commentRequests,
		totalPrice: roundMoney(
			suggestions.totalPrice + search.totalPrice + comments.totalPrice,
		),
		currency: search.currency,
	};
}

async function runTikHubAdmin(endpoint, params, options) {
	let lastError;
	for (let attempt = 0; attempt < 3; attempt++) {
		try {
			return await runTikHub(endpoint, params, options);
		} catch (error) {
			lastError = error;
			if (
				!/HTTP 429|too many requests/i.test(String(error?.message ?? error)) ||
				attempt === 2
			)
				throw error;
			await delay(1_100 * (attempt + 1), options.signal);
		}
	}
	throw lastError;
}

function delay(milliseconds, signal) {
	return new Promise((resolve, reject) => {
		const timer = setTimeout(resolve, milliseconds);
		if (signal) {
			const abort = () => {
				clearTimeout(timer);
				reject(new Error("TikHub administrative request aborted"));
			};
			if (signal.aborted) abort();
			else signal.addEventListener("abort", abort, { once: true });
		}
	});
}

export function unwrapTikHubData(response) {
	let value = response;
	for (let i = 0; i < 4; i++) {
		if (
			value &&
			typeof value === "object" &&
			!Array.isArray(value) &&
			value.data &&
			typeof value.data === "object"
		) {
			value = value.data;
		} else break;
	}
	return value;
}

export function roundMoney(value) {
	return Math.round((Number(value) + Number.EPSILON) * 1_000_000) / 1_000_000;
}
