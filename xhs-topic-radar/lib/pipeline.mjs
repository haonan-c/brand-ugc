import { open, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { createConfigSignature, loadConfig } from "./config.mjs";
import {
	createRun,
	getRecentTopicTitles,
	openDatabase,
	updateRun,
	upsertSourceItem,
} from "./database.mjs";
import {
	deduplicateNotes,
	extractCommentTexts,
	extractItems,
	extractSuggestionTerms,
	normalizeNote,
	selectBalanced,
	toEvidenceItem,
} from "./normalize.mjs";
import {
	getRunPricing,
	getTikHubUserInfo,
	roundMoney,
	runTikHub,
	TIKHUB_ENDPOINTS,
} from "./tikhub.mjs";

/**
 * @param {{ workspace?: string, force?: boolean, suggestionPlan?: any, apiKey?: string, signal?: AbortSignal, onProgress?: (message: string) => void }} [options]
 */
export async function runCollection({
	workspace = process.cwd(),
	force = false,
	suggestionPlan,
	apiKey = process.env.TIKHUB_API_KEY,
	signal,
	onProgress,
} = {}) {
	workspace = resolve(workspace);
	const { config, path: configPath } = await loadConfig(workspace);
	const runDate = localDate();
	const reportPath = join(workspace, config.report.directory, `${runDate}.md`);
	const configSignature = createConfigSignature(config);
	if (!force && (await findCachedReport(workspace, config, runDate))) {
		return { cached: true, reportPath, runDate };
	}
	if (!apiKey) throw new Error("TIKHUB_API_KEY is not configured");

	const dataDir = join(workspace, "data");
	const pendingDir = join(dataDir, "pending");
	const rawDir = join(dataDir, "raw", runDate);
	await Promise.all([
		mkdir(pendingDir, { recursive: true }),
		mkdir(rawDir, { recursive: true }),
	]);
	const lockPath = join(dataDir, "topic-radar.lock");
	let lock;
	try {
		lock = await open(lockPath, "wx");
	} catch (error) {
		if (error.code === "EEXIST")
			throw new Error("Another topic radar run is already active");
		throw error;
	}

	const startedAt = new Date().toISOString();
	const runId = `${runDate}-${startedAt.replace(/\D/g, "").slice(8, 14)}`;
	const db = openDatabase(workspace);
	createRun(db, {
		runId,
		runDate,
		provider: "tikhub",
		status: "collecting",
		startedAt,
	});
	let requestCount = suggestionPlan?.requestCount ?? 0;
	let estimatedCostUsd = suggestionPlan?.estimatedCostUsd ?? 0;
	const errors = [...(suggestionPlan?.errors ?? [])];
	const notes = [];
	const searchSuggestions = structuredClone(
		suggestionPlan?.searchSuggestions ?? [],
	);
	let pricing = suggestionPlan?.pricing;

	try {
		if (suggestionPlan) {
			if (suggestionPlan.configSignature !== configSignature) {
				throw new Error(
					"Demand-discovery plan does not match the current industry/time configuration",
				);
			}
			if (suggestionPlan.runDate !== runDate)
				throw new Error("Demand-discovery plan has expired; run /topics again");
			validatePreflight(pricing, config);
		} else {
			onProgress?.("正在通过 TikHub 官方定价接口执行费用预检");
			pricing = await getRunPricing(config, { signal, apiKey });
			validatePreflight(pricing, config);
			const user = await getTikHubUserInfo({
				apiKey,
				baseUrl: config.tikhub.baseUrl,
				timeoutMs: config.collection.commandTimeoutMs,
				signal,
			});
			const available =
				Number(user.balance ?? 0) + Number(user.free_credit ?? 0);
			if (Number.isFinite(available) && available < pricing.totalPrice) {
				throw new Error(
					`TikHub balance is insufficient for the bounded run: US$${available.toFixed(4)} < US$${pricing.totalPrice.toFixed(4)}`,
				);
			}
		}

		let nextPaidRequestAt = suggestionPlan
			? new Date(suggestionPlan.completedAt).getTime() +
				config.collection.minRequestIntervalMs
			: 0;
		const pacePaidRequest = async () => {
			const waitMs = Math.max(0, nextPaidRequestAt - Date.now());
			if (waitMs > 0) await delay(waitMs, signal);
			nextPaidRequestAt = Date.now() + config.collection.minRequestIntervalMs;
		};
		const chargeAttempt = (unitCost) => {
			const nextCount = requestCount + 1;
			const nextCost = roundMoney(estimatedCostUsd + unitCost);
			if (nextCount > config.tikhub.maxRequestsPerRun) {
				throw new Error(
					`TikHub request cap exceeded: ${nextCount} > ${config.tikhub.maxRequestsPerRun}`,
				);
			}
			if (nextCost > config.tikhub.maxEstimatedCostUsd) {
				throw new Error(
					`TikHub cost cap exceeded: US$${nextCost} > US$${config.tikhub.maxEstimatedCostUsd}`,
				);
			}
			requestCount = nextCount;
			estimatedCostUsd = nextCost;
		};

		if (!suggestionPlan) {
			onProgress?.(
				`正在采集 ${config.collection.suggestionSeeds.length} 组小红书搜索联想词`,
			);
			for (
				let index = 0;
				index < config.collection.suggestionSeeds.length;
				index++
			) {
				const seed = config.collection.suggestionSeeds[index];
				onProgress?.(
					`[联想 ${index + 1}/${config.collection.suggestionSeeds.length}] ${seed.keyword}`,
				);
				await pacePaidRequest();
				chargeAttempt(pricing.suggestions.basePrice);
				try {
					const response = await runTikHub(
						TIKHUB_ENDPOINTS.searchSuggest,
						{
							keyword: seed.keyword,
						},
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
							`suggest-${String(index + 1).padStart(2, "0")}-${safeName(seed.keyword)}.json`,
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
		}

		onProgress?.(`正在搜索 ${config.queries.length} 组关键词（TikHub）`);
		for (let index = 0; index < config.queries.length; index++) {
			const query = config.queries[index];
			onProgress?.(`[${index + 1}/${config.queries.length}] ${query.keyword}`);
			await pacePaidRequest();
			chargeAttempt(pricing.search.basePrice);
			try {
				const response = await runTikHub(
					TIKHUB_ENDPOINTS.searchNotes,
					{
						keyword: query.keyword,
						page: 1,
						sort_type: "general",
						note_type: "不限",
						time_filter: toTikHubTimeFilter(config.lookbackDays),
						ai_mode: 0,
					},
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
						`search-${String(index + 1).padStart(2, "0")}-${safeName(query.keyword)}.json`,
					),
					JSON.stringify(response, null, 2),
				);
				const items = extractItems(response).slice(
					0,
					config.collection.maxItemsPerQuery,
				);
				for (const [itemIndex, raw] of items.entries()) {
					const note = normalizeNote(raw, query, startedAt, itemIndex + 1);
					if (isWithinLookback(note, startedAt, config.lookbackDays))
						notes.push(note);
				}
			} catch (error) {
				errors.push({
					stage: `search:${query.keyword}`,
					message: cleanError(error),
				});
			}
		}

		const uniqueNotes = deduplicateNotes(notes);
		if (uniqueNotes.length === 0)
			throw new Error(
				`No XHS notes collected; errors: ${errors.map((e) => e.message).join(" | ")}`,
			);
		for (const note of uniqueNotes) upsertSourceItem(db, runId, note);

		const commentTargets = selectBalanced(
			uniqueNotes,
			config.audienceQuotas,
			config.collection.maxCommentNotes,
		).filter((note) => note.noteId);
		onProgress?.(`正在采样 ${commentTargets.length} 篇笔记的评论（TikHub）`);
		let commentNotes = 0;
		for (let index = 0; index < commentTargets.length; index++) {
			const note = commentTargets[index];
			onProgress?.(
				`[评论 ${index + 1}/${commentTargets.length}] ${note.title.slice(0, 28)}`,
			);
			await pacePaidRequest();
			chargeAttempt(pricing.comments.basePrice);
			try {
				const response = await runTikHub(
					TIKHUB_ENDPOINTS.noteComments,
					{
						note_id: note.noteId,
						cursor: "",
						index: 0,
						pageArea: "UNFOLDED",
						sort_strategy: "latest_v2",
					},
					{
						apiKey,
						baseUrl: config.tikhub.baseUrl,
						timeoutMs: config.collection.commandTimeoutMs,
						signal,
					},
				);
				note.commentTexts = extractCommentTexts(response).slice(
					0,
					config.collection.maxCommentsPerNote,
				);
				commentNotes++;
				await writeFile(
					join(
						rawDir,
						`comments-${String(index + 1).padStart(2, "0")}-${safeName(note.identity)}.json`,
					),
					JSON.stringify(response, null, 2),
				);
			} catch (error) {
				errors.push({
					stage: `comments:${note.identity}`,
					message: cleanError(error),
				});
			}
		}

		const recentTitles = getRecentTopicTitles(
			db,
			config.history.topicDedupDays,
		);
		const evidenceNotes = selectEvidenceNotes(
			uniqueNotes.filter((note) => note.noteUrl),
			config.queries,
			config.audienceQuotas,
			config.collection.maxEvidenceItems,
		);
		const marketOverview = buildMarketOverview(evidenceNotes, config);
		const keywordBenchmarks = buildKeywordBenchmarks(evidenceNotes, config);
		const pending = {
			version: 3,
			provider: "tikhub",
			runId,
			runDate,
			startedAt,
			configPath,
			configSignature,
			industry: config.industry,
			lookbackDays: config.lookbackDays,
			outputCount: config.outputCount,
			audienceLabels: config.audienceLabels,
			audienceQuotas: config.audienceQuotas,
			requestCount,
			estimatedCostUsd,
			pricing,
			queries: config.queries,
			searchSuggestions,
			stats: {
				collectedNotes: notes.length,
				uniqueNotes: uniqueNotes.length,
				commentNotes,
				suggestionTerms: searchSuggestions.reduce(
					(sum, group) => sum + group.terms.length,
					0,
				),
			},
			errors,
			recentTopicTitles: recentTitles,
			marketOverview,
			keywordBenchmarks,
			evidence: evidenceNotes.map(toEvidenceItem),
		};
		const pendingPath = join(pendingDir, `${runId}.json`);
		await writeFile(pendingPath, JSON.stringify(pending, null, 2), "utf8");
		updateRun(db, runId, {
			status: "awaiting_finalize",
			estimatedCostUsd,
			requestCount,
			noteCount: uniqueNotes.length,
			errorCount: errors.length,
			errorsJson: JSON.stringify(errors),
			pendingPath,
		});
		onProgress?.(
			`采集完成：${uniqueNotes.length} 篇去重笔记，等待 Pi 生成选题`,
		);
		return {
			cached: false,
			runId,
			runDate,
			pendingPath,
			requestCount,
			estimatedCostUsd,
			stats: pending.stats,
			errors,
		};
	} catch (error) {
		updateRun(db, runId, {
			status: "failed",
			completedAt: new Date().toISOString(),
			estimatedCostUsd,
			requestCount,
			errorCount: errors.length + 1,
			errorsJson: JSON.stringify([
				...errors,
				{ stage: "pipeline", message: cleanError(error) },
			]),
		});
		throw error;
	} finally {
		db.close();
		await lock?.close().catch(() => {});
		await rm(lockPath, { force: true }).catch(() => {});
	}
}

export function buildFinalizationPrompt(result) {
	return [
		"请执行小红书每日选题生成。",
		`读取证据包：${result.pendingPath}`,
		"严格基于证据包的 industry、outputCount、audienceLabels 和 audienceQuotas 生成选题；数量与每类配额必须完全一致。",
		"参考 marketOverview、keywordBenchmarks、评论问题和证据笔记，把每个方向写成可直接进入创作的策略卡：明确目标场景、内容缺口、内容结构、标题公式、写作框架、开头钩子、必须覆盖点、正文提纲和 CTA。",
		"scoreBreakdown 必须分别评价需求匹配、证据强度、时机、差异化、可执行性和风险安全；score = 四舍五入(需求匹配×25% + 证据强度×20% + 时机×15% + 差异化×15% + 可执行性×15% + 风险安全×10%)。priority：80分及以上 high，65-79分 medium，低于65分 low。不要用一个无法解释的主观总分。",
		"每个选题至少引用一个证据包中原样存在的 noteUrl，优先引用两个互相支持的来源；不得修改、重建或截断 URL。evidenceSummary 必须说明这些证据具体支持什么，不能只写‘热度高’。",
		"每个选题的 demandKeywords 必须使用其对应 audience 的 searchSuggestions 中原样存在的 seed 或 terms；这是搜索联想需求信号，不得表述成精确搜索量。",
		"单次搜索快照只能支持当前样本的相对判断：不得声称精确搜索量、全平台趋势、算法偏好或必然爆款。内容缺口属于基于样本的策略推断，必须用审慎措辞。",
		"不得把小红书笔记当作事实或政策权威；涉及价格、时效、资格、效果、政策或合规结论时，riskNote 和 doNotSay 必须明确要求核验官方或权威来源并禁止结果承诺。",
		"避免与 recentTopicTitles 重复。最后必须调用 topic_finalize_report，runId 使用证据包中的值。",
		"工具调用成功后必须给用户一段简洁的完成总结：明确报告已完成、报告路径、Top 3 选题、请求次数与预计费用、证据数量、采集异常数量。不要重复粘贴整份报告。",
	].join("\n");
}

function validatePreflight(pricing, config) {
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

export async function findCachedReport(
	workspace,
	config,
	runDate = localDate(),
) {
	const reportPath = join(workspace, config.report.directory, `${runDate}.md`);
	const structuredReportPath = join(
		workspace,
		config.report.directory,
		`${runDate}.json`,
	);
	if (!existsSync(reportPath)) return null;
	return (await reportMatchesConfig(
		structuredReportPath,
		createConfigSignature(config),
	))
		? reportPath
		: null;
}

async function reportMatchesConfig(structuredReportPath, configSignature) {
	if (!existsSync(structuredReportPath)) return false;
	try {
		const report = JSON.parse(await readFile(structuredReportPath, "utf8"));
		return report.configSignature === configSignature;
	} catch {
		return false;
	}
}

function selectEvidenceNotes(notes, queries, quotas, limit) {
	const selected = [];
	const used = new Set();
	const perQueryTarget = Math.max(
		2,
		Math.floor(limit / Math.max(1, queries.length)),
	);
	const add = (note) => {
		if (!note || used.has(note.identity) || selected.length >= limit) return;
		selected.push(note);
		used.add(note.identity);
	};

	for (const query of queries) {
		notes
			.filter((note) => note.matchedKeyword === query.keyword)
			.sort(
				(a, b) =>
					(a.searchRank ?? 999) - (b.searchRank ?? 999) ||
					b.preliminaryScore - a.preliminaryScore,
			)
			.slice(0, perQueryTarget)
			.forEach(add);
	}
	for (const note of selectBalanced(notes, quotas, limit)) add(note);
	for (const note of [...notes].sort(
		(a, b) => b.preliminaryScore - a.preliminaryScore,
	))
		add(note);
	return selected;
}

function buildMarketOverview(notes, config) {
	const audiences = Object.keys(config.audienceQuotas).map((audience) => {
		const sample = notes.filter((note) => note.audience === audience);
		return {
			audience,
			label: config.audienceLabels[audience] ?? audience,
			evidenceCount: sample.length,
			avgLikes: average(sample.map((note) => note.likes)),
			avgCollects: average(sample.map((note) => note.collects)),
			avgComments: average(sample.map((note) => note.comments)),
			savesLikesRatio: ratio(
				sample.reduce((sum, note) => sum + note.collects, 0),
				sample.reduce((sum, note) => sum + note.likes, 0),
			),
			topEvidenceTitles: [...sample]
				.sort((a, b) => b.preliminaryScore - a.preliminaryScore)
				.slice(0, 3)
				.map((note) => note.title),
		};
	});
	return {
		evidenceCount: notes.length,
		audiences,
		caveat:
			"互动数据来自本次有限搜索证据样本，只用于相对判断，不代表全平台搜索量、排名规律或趋势因果。",
	};
}

function buildKeywordBenchmarks(notes, config) {
	return config.queries
		.map((query) => {
			const sample = notes
				.filter((note) => note.matchedKeyword === query.keyword)
				.sort(
					(a, b) =>
						(a.searchRank ?? 999) - (b.searchRank ?? 999) ||
						b.preliminaryScore - a.preliminaryScore,
				);
			return {
				audience: query.audience,
				keyword: query.keyword,
				evidenceCount: sample.length,
				avgLikes: average(sample.map((note) => note.likes)),
				avgCollects: average(sample.map((note) => note.collects)),
				avgComments: average(sample.map((note) => note.comments)),
				savesLikesRatio: ratio(
					sample.reduce((sum, note) => sum + note.collects, 0),
					sample.reduce((sum, note) => sum + note.likes, 0),
				),
				notes: sample.slice(0, 5).map((note) => ({
					searchRank: note.searchRank,
					title: note.title,
					description: note.description.slice(0, 500),
					publishTime: note.publishTime,
					metrics: {
						likes: note.likes,
						collects: note.collects,
						comments: note.comments,
						shares: note.shares,
					},
					commentQuestions: note.commentTexts.slice(0, 6),
					noteUrl: note.noteUrl,
				})),
			};
		})
		.filter((item) => item.evidenceCount > 0);
}

function average(values) {
	if (values.length === 0) return 0;
	return Math.round(
		values.reduce((sum, value) => sum + value, 0) / values.length,
	);
}

function ratio(numerator, denominator) {
	return denominator > 0 ? Number((numerator / denominator).toFixed(2)) : 0;
}

function isWithinLookback(note, startedAt, lookbackDays) {
	if (!note.publishTime) return true;
	const published = new Date(note.publishTime).getTime();
	const end = new Date(startedAt).getTime();
	if (!Number.isFinite(published) || !Number.isFinite(end)) return true;
	return (
		published >= end - lookbackDays * 86_400_000 &&
		published <= end + 86_400_000
	);
}

function toTikHubTimeFilter(days) {
	if (days <= 1) return "一天内";
	if (days <= 7) return "一周内";
	if (days <= 180) return "半年内";
	return "不限";
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

function delay(milliseconds, signal) {
	return new Promise((resolve, reject) => {
		const timer = setTimeout(done, milliseconds);
		const abort = () => {
			clearTimeout(timer);
			signal?.removeEventListener("abort", abort);
			reject(new Error("Topic radar collection aborted"));
		};
		function done() {
			signal?.removeEventListener("abort", abort);
			resolve();
		}
		if (signal?.aborted) abort();
		else signal?.addEventListener("abort", abort, { once: true });
	});
}

function localDate(date = new Date()) {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const day = String(date.getDate()).padStart(2, "0");
	return `${year}-${month}-${day}`;
}
