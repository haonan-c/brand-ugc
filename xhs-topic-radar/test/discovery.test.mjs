import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { discoverSearchSuggestions } from "../lib/discovery.mjs";

const defaults = JSON.parse(
	await readFile(
		new URL("../config/default-topic-radar.json", import.meta.url),
		"utf8",
	),
);

test("demand discovery spends only suggestion requests and persists a review plan", async () => {
	const workspace = await mkdtemp(join(tmpdir(), "topic-discovery-"));
	const config = structuredClone(defaults);
	config.collection.minRequestIntervalMs = 0;
	const originalFetch = globalThis.fetch;
	const apiKey = "test-token-1234567890";
	globalThis.fetch = async (input, init) => {
		assert.equal(init?.headers?.Authorization, `Bearer ${apiKey}`);
		const url = new URL(String(input));
		if (url.pathname.endsWith("/calculate_price")) {
			const count = Number(url.searchParams.get("request_per_day"));
			return Response.json({
				code: 200,
				data: { base_price: 0.01, total_price: count * 0.01, currency: "USD" },
			});
		}
		if (url.pathname.endsWith("/get_user_info")) {
			return Response.json({
				code: 200,
				user_data: { balance: 10, free_credit: 0 },
			});
		}
		if (url.pathname.endsWith("/fetch_search_suggest")) {
			const keyword = url.searchParams.get("keyword");
			return Response.json({
				code: 200,
				data: { data: { sug_items: [{ text: `${keyword}需求词` }] } },
			});
		}
		throw new Error(`Unexpected URL: ${url}`);
	};

	try {
		const plan = await discoverSearchSuggestions({ workspace, config, apiKey });
		assert.equal(plan.requestCount, 3);
		assert.equal(plan.estimatedCostUsd, 0.03);
		assert.equal(plan.searchSuggestions.length, 3);
		assert.ok(
			plan.searchSuggestions.every((group) => group.terms.length === 1),
		);
		assert.equal(
			JSON.parse(await readFile(plan.planPath, "utf8")).planId,
			plan.planId,
		);
	} finally {
		globalThis.fetch = originalFetch;
	}
});
