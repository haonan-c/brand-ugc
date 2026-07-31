import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { loadConfig } from "./config.mjs";
import { openDatabase, saveCandidates, updateRun } from "./database.mjs";

const AUDIENCE_LABELS = {
	student: "全国高校大学生",
	high_tech_enterprise: "高新技术企业",
	hangzhou_e_talent: "杭州E类人才",
};

const SCORE_WEIGHTS = {
	demandFit: 0.25,
	evidenceStrength: 0.2,
	timingFit: 0.15,
	differentiation: 0.15,
	executability: 0.15,
	riskSafety: 0.1,
};
const SCORE_LABELS = {
	demandFit: "需求匹配",
	evidenceStrength: "证据强度",
	timingFit: "时机",
	differentiation: "差异化",
	executability: "可执行性",
	riskSafety: "风险安全",
};
const PRIORITY_LABELS = { high: "高优先", medium: "中优先", low: "低优先" };
const DIFFICULTY_LABELS = { easy: "低", medium: "中", hard: "高" };
const STRUCTURE_LABELS = {
	listicle: "清单合集型",
	tutorial: "教程攻略型",
	review: "测评体验型",
	comparison: "对比分析型",
	"experience-share": "经验分享型",
	"product-rec": "产品推荐型",
	knowledge: "科普知识型",
	"news-update": "资讯更新型",
};
const TITLE_PATTERN_LABELS = {
	number: "数字式",
	question: "提问式",
	"pain-point": "痛点式",
	result: "结果式",
	urgency: "紧迫式",
	authority: "权威式",
};
const FRAMEWORK_LABELS = {
	"listicle-authority": "清单权威型",
	"tutorial-stepbystep": "教程步骤型",
	"experience-storytelling": "经验叙事型",
	"comparison-matrix": "对比矩阵型",
};
const REQUIRED_TEXT_FIELDS = {
	title: 6,
	whyNow: 10,
	userQuestion: 4,
	targetScenario: 6,
	angle: 8,
	contentGap: 8,
	evidenceSummary: 12,
	contentFormat: 2,
	hook: 8,
	callToAction: 6,
	riskNote: 8,
};
const TOPIC_ENUMS = {
	contentStructure: new Set(Object.keys(STRUCTURE_LABELS)),
	titlePattern: new Set(Object.keys(TITLE_PATTERN_LABELS)),
	writingFramework: new Set(Object.keys(FRAMEWORK_LABELS)),
	priority: new Set(["high", "medium", "low"]),
	difficulty: new Set(["easy", "medium", "hard"]),
};
const GUARDED_CLAIM_PATTERN =
	/价格|费用|时效|多久|资格|效果|政策|合规|通过|下证|认定|补贴|福利|加分/;

export async function finalizeReport({ workspace, runId, topics }) {
	const { config } = await loadConfig(workspace);
	const pendingPath = join(workspace, "data", "pending", `${runId}.json`);
	if (!existsSync(pendingPath))
		throw new Error(`Pending run not found: ${runId}`);
	let pending;
	try {
		pending = JSON.parse(await readFile(pendingPath, "utf8"));
	} catch (error) {
		throw new Error(`Pending run is unreadable or invalid JSON: ${runId}`, {
			cause: error,
		});
	}
	validateTopics(topics, pending, config);

	const reportDir = resolve(workspace, config.report.directory);
	await mkdir(reportDir, { recursive: true });
	const reportPath = join(reportDir, `${pending.runDate}.md`);
	const latestPath = join(reportDir, config.report.latestFilename);
	const markdown = renderMarkdown(pending, topics);
	await writeFile(reportPath, markdown, "utf8");
	await copyFile(reportPath, latestPath);
	await writeFile(
		join(reportDir, `${pending.runDate}.json`),
		JSON.stringify({ ...pending, topics }, null, 2),
		"utf8",
	);

	const db = openDatabase(workspace);
	try {
		saveCandidates(db, runId, topics);
		updateRun(db, runId, {
			status: "completed",
			completedAt: new Date().toISOString(),
			reportPath,
		});
	} finally {
		db.close();
	}
	const priorityCounts = topics.reduce((counts, topic) => {
		counts[topic.priority] = (counts[topic.priority] ?? 0) + 1;
		return counts;
	}, {});
	const topTopics = [...topics]
		.sort((a, b) => b.score - a.score)
		.slice(0, 3)
		.map((topic) => ({
			title: topic.title,
			score: topic.score,
			priority: topic.priority,
			audience:
				pending.audienceLabels?.[topic.audience] ??
				AUDIENCE_LABELS[topic.audience] ??
				topic.audience,
		}));
	return {
		reportPath,
		latestPath,
		count: topics.length,
		summary: {
			industry: pending.industry ?? "小红书",
			runDate: pending.runDate,
			requestCount: pending.requestCount ?? 0,
			estimatedCostUsd: Number(pending.estimatedCostUsd ?? 0),
			evidenceCount: pending.evidence?.length ?? 0,
			collectionErrorCount: pending.errors?.length ?? 0,
			priorityCounts,
			topTopics,
		},
	};
}

export function validateTopics(topics, pending, config) {
	if (!Array.isArray(topics) || topics.length !== config.outputCount) {
		throw new Error(`Expected exactly ${config.outputCount} topics`);
	}
	const counts = {};
	const allowedUrls = new Set(
		pending.evidence.map((item) => item.noteUrl).filter(Boolean),
	);
	const demandByAudience = new Map();
	for (const group of pending.searchSuggestions ?? []) {
		const terms = demandByAudience.get(group.audience) ?? new Set();
		terms.add(group.seed);
		for (const term of group.terms ?? []) terms.add(term);
		demandByAudience.set(group.audience, terms);
	}
	const titles = new Set();
	const recentTitles = new Set(
		(pending.recentTopicTitles ?? []).map((title) =>
			String(title).trim().toLowerCase(),
		),
	);
	for (const [index, topic] of topics.entries()) {
		if (!Object.hasOwn(config.audienceQuotas, topic.audience)) {
			throw new Error(`Topic ${index + 1} uses unknown audience: ${topic.audience}`);
		}
		counts[topic.audience] = (counts[topic.audience] ?? 0) + 1;
		for (const [field, minLength] of Object.entries(REQUIRED_TEXT_FIELDS)) {
			if (typeof topic[field] !== "string" || topic[field].trim().length < minLength) {
				throw new Error(
					`Topic ${index + 1} ${field} must contain at least ${minLength} characters`,
				);
			}
		}
		for (const [field, allowed] of Object.entries(TOPIC_ENUMS)) {
			if (!allowed.has(topic[field])) {
				throw new Error(`Topic ${index + 1} has invalid ${field}: ${topic[field]}`);
			}
		}
		const normalizedTitle = topic.title.trim().toLowerCase();
		if (titles.has(normalizedTitle))
			throw new Error(`Duplicate topic title: ${topic.title}`);
		if (recentTitles.has(normalizedTitle)) {
			throw new Error(`Topic title repeats recent history: ${topic.title}`);
		}
		titles.add(normalizedTitle);
		if (
			!Array.isArray(topic.sourceUrls) ||
			topic.sourceUrls.length === 0 ||
			topic.sourceUrls.length > 5
		) {
			throw new Error(`Topic ${index + 1} must cite at least one source URL`);
		}
		for (const url of topic.sourceUrls) {
			if (!allowedUrls.has(url))
				throw new Error(
					`Topic ${index + 1} cites unknown or modified URL: ${url}`,
				);
		}
		const allowedDemand = demandByAudience.get(topic.audience);
		if (allowedDemand) {
			if (
				!Array.isArray(topic.demandKeywords) ||
				topic.demandKeywords.length === 0 ||
				topic.demandKeywords.length > 3 ||
				topic.demandKeywords.some(
					(value) => typeof value !== "string" || value.trim().length < 2,
				)
			) {
				throw new Error(
					`Topic ${index + 1} must cite one to three search demand keywords`,
				);
			}
			for (const keyword of topic.demandKeywords) {
				if (!allowedDemand.has(keyword)) {
					throw new Error(
						`Topic ${index + 1} cites an unknown demand keyword for ${topic.audience}: ${keyword}`,
					);
				}
			}
		}
		if (!topic.scoreBreakdown || typeof topic.scoreBreakdown !== "object") {
			throw new Error(`Topic ${index + 1} needs an explainable scoreBreakdown`);
		}
		for (const key of Object.keys(SCORE_WEIGHTS)) {
			const value = topic.scoreBreakdown[key];
			if (!Number.isInteger(value) || value < 0 || value > 100) {
				throw new Error(
					`Topic ${index + 1} scoreBreakdown.${key} must be an integer from 0 to 100`,
				);
			}
		}
		const expectedScore = calculateScore(topic.scoreBreakdown);
		if (topic.score !== expectedScore) {
			throw new Error(
				`Topic ${index + 1} score must equal weighted breakdown ${expectedScore}, got ${topic.score}`,
			);
		}
		const expectedPriority = priorityForScore(topic.score);
		if (topic.priority !== expectedPriority) {
			throw new Error(
				`Topic ${index + 1} priority must be ${expectedPriority} for score ${topic.score}`,
			);
		}
		if (
			!Array.isArray(topic.titleAlternatives) ||
			topic.titleAlternatives.length < 2 ||
			topic.titleAlternatives.length > 4 ||
			topic.titleAlternatives.some(
				(value) => typeof value !== "string" || value.trim().length < 6,
			)
		) {
			throw new Error(
				`Topic ${index + 1} needs two to four title alternatives of at least six characters`,
			);
		}
		if (
			!Array.isArray(topic.mustCover) ||
			topic.mustCover.length < 2 ||
			topic.mustCover.length > 6 ||
			topic.mustCover.some(
				(value) => typeof value !== "string" || value.trim().length < 2,
			)
		) {
			throw new Error(
				`Topic ${index + 1} needs two to six must-cover points`,
			);
		}
		if (
			!Array.isArray(topic.outline) ||
			topic.outline.length < 3 ||
			topic.outline.length > 7 ||
			topic.outline.some(
				(value) => typeof value !== "string" || value.trim().length < 4,
			)
		) {
			throw new Error(`Topic ${index + 1} needs three to seven outline steps`);
		}
		if (
			!Array.isArray(topic.doNotSay) ||
			topic.doNotSay.length < 1 ||
			topic.doNotSay.length > 4 ||
			topic.doNotSay.some(
				(value) => typeof value !== "string" || value.trim().length < 4,
			)
		) {
			throw new Error(
				`Topic ${index + 1} needs one to four do-not-say guardrails`,
			);
		}
		const claimText = [
			topic.title,
			topic.userQuestion,
			topic.angle,
			topic.whyNow,
		].join(" ");
		if (GUARDED_CLAIM_PATTERN.test(claimText)) {
			if (!/官方|权威/.test(topic.riskNote)) {
				throw new Error(
					`Topic ${index + 1} riskNote must require official or authoritative verification`,
				);
			}
			if (!/承诺|保证|一定|必然/.test(topic.doNotSay.join(" "))) {
				throw new Error(
					`Topic ${index + 1} doNotSay must prohibit outcome guarantees`,
				);
			}
		}
	}
	for (const [audience, quota] of Object.entries(config.audienceQuotas)) {
		if ((counts[audience] ?? 0) !== quota) {
			throw new Error(
				`Audience ${audience} requires ${quota} topics, got ${counts[audience] ?? 0}`,
			);
		}
	}
}

function renderMarkdown(pending, topics) {
	const costLine =
		pending.provider === "tikhub"
			? `- 数据服务：TikHub；API 请求 ${pending.requestCount} 次；预计成本 US$${Number(pending.estimatedCostUsd).toFixed(2)}`
			: `- 预计消耗：${pending.estimatedCredits} 积分（约 ¥${(pending.estimatedCredits * 0.01).toFixed(2)}）`;
	const lines = [
		`# ${pending.industry ?? "小红书"}每日选题日报｜${pending.runDate}`,
		"",
		`- 运行编号：\`${pending.runId}\``,
		`- 数据窗口：最近 ${pending.lookbackDays} 天`,
		`- 原始去重笔记：${pending.stats.uniqueNotes} 条`,
		`- 评论采样笔记：${pending.stats.commentNotes} 条`,
		`- 小红书搜索联想词：${pending.stats.suggestionTerms ?? 0} 个`,
		costLine,
		`- 采集异常：${pending.errors.length} 项`,
		"",
		"> 选题来自社媒信号，不代表事实或政策权威。涉及价格、时效、资格、效果、政策或合规结论时，发布前必须核验官方或权威来源。",
		"",
	];

	lines.push("## 今日决策摘要", "");
	lines.push(
		"| 排名 | 选题 | 人群 | 优先级 | 总分 | 难度 |",
		"|---:|---|---|---|---:|---|",
	);
	[...topics]
		.sort((a, b) => b.score - a.score)
		.slice(0, 5)
		.forEach((topic, index) =>
			lines.push(
				`| ${index + 1} | ${escapeTable(topic.title)} | ${pending.audienceLabels?.[topic.audience] ?? AUDIENCE_LABELS[topic.audience] ?? topic.audience} | ${PRIORITY_LABELS[topic.priority] ?? topic.priority} | ${topic.score} | ${DIFFICULTY_LABELS[topic.difficulty] ?? topic.difficulty} |`,
			),
		);
	lines.push("");

	if (pending.marketOverview?.audiences?.length) {
		lines.push("## 样本市场概览", "");
		lines.push(
			"| 人群 | 证据样本 | 平均点赞 | 平均收藏 | 平均评论 | 收藏/点赞比 |",
			"|---|---:|---:|---:|---:|---:|",
		);
		for (const item of pending.marketOverview.audiences) {
			lines.push(
				`| ${escapeTable(item.label)} | ${item.evidenceCount} | ${item.avgLikes} | ${item.avgCollects} | ${item.avgComments} | ${Number(item.savesLikesRatio).toFixed(2)} |`,
			);
		}
		lines.push("", `> ${pending.marketOverview.caveat}`, "");
	}

	lines.push("## 选题策略卡", "");
	topics.forEach((topic, index) => {
		lines.push(`### ${index + 1}. ${topic.title}`);
		lines.push("");
		lines.push(
			`- **人群**：${pending.audienceLabels?.[topic.audience] ?? AUDIENCE_LABELS[topic.audience] ?? topic.audience}`,
		);
		lines.push(
			`- **决策**：${PRIORITY_LABELS[topic.priority] ?? topic.priority}｜推荐分 ${topic.score}｜竞争执行难度 ${DIFFICULTY_LABELS[topic.difficulty] ?? topic.difficulty}`,
		);
		lines.push(`- **用户原始问题**：${topic.userQuestion}`);
		lines.push(`- **目标场景**：${topic.targetScenario}`);
		lines.push(`- **为什么现在做**：${topic.whyNow}`);
		lines.push(`- **样本内容缺口**：${topic.contentGap}`);
		lines.push(`- **推荐角度**：${topic.angle}`);
		lines.push(`- **证据解读**：${topic.evidenceSummary}`);
		lines.push(
			`- **搜索需求词**：${(topic.demandKeywords ?? []).map((word) => `\`${word}\``).join("、") || "未采集"}`,
		);
		lines.push("");
		lines.push("#### 创作执行", "");
		lines.push(`- **内容形式**：${topic.contentFormat}`);
		lines.push(
			`- **内容结构**：${STRUCTURE_LABELS[topic.contentStructure] ?? topic.contentStructure}`,
		);
		lines.push(
			`- **标题公式**：${TITLE_PATTERN_LABELS[topic.titlePattern] ?? topic.titlePattern}`,
		);
		lines.push(
			`- **写作框架**：${FRAMEWORK_LABELS[topic.writingFramework] ?? topic.writingFramework}`,
		);
		lines.push(`- **开头钩子**：${topic.hook}`);
		lines.push(`- **行动引导**：${topic.callToAction}`);
		lines.push("- **必须覆盖**：");
		topic.mustCover.forEach((point) => lines.push(`  - ${point}`));
		lines.push("- **正文提纲**：");
		topic.outline.forEach((point, i) => lines.push(`  ${i + 1}. ${point}`));
		lines.push("- **标题备选**：");
		topic.titleAlternatives.forEach((title, i) =>
			lines.push(`  ${i + 1}. ${title}`),
		);
		lines.push("");
		lines.push("#### 评分与风控", "");
		lines.push(
			`- **评分拆解**：${Object.entries(SCORE_LABELS)
				.map(([key, label]) => `${label} ${topic.scoreBreakdown[key]}`)
				.join("｜")}`,
		);
		lines.push(`- **风险提示**：${topic.riskNote}`);
		lines.push("- **禁止表述**：");
		topic.doNotSay.forEach((item) => lines.push(`  - ${item}`));
		lines.push("- **来源证据**：");
		topic.sourceUrls.forEach((url, i) =>
			lines.push(`  ${i + 1}. [小红书来源 ${i + 1}](${url})`),
		);
		lines.push("");
	});

	if (pending.keywordBenchmarks?.length) {
		lines.push("## 关键词证据样本基准", "");
		lines.push(
			"| 搜索关键词 | 样本数 | 平均点赞 | 平均收藏 | 平均评论 | 收藏/点赞比 |",
			"|---|---:|---:|---:|---:|---:|",
		);
		for (const item of pending.keywordBenchmarks) {
			lines.push(
				`| ${escapeTable(item.keyword)} | ${item.evidenceCount} | ${item.avgLikes} | ${item.avgCollects} | ${item.avgComments} | ${Number(item.savesLikesRatio).toFixed(2)} |`,
			);
		}
		lines.push(
			"",
			"> 这些数字只描述报告内的有限证据样本，不是全平台基准或搜索排名门槛。",
			"",
		);
	}

	if (pending.searchSuggestions?.length) {
		lines.push("## 小红书搜索联想需求词", "");
		for (const group of pending.searchSuggestions) {
			lines.push(
				`- **${pending.audienceLabels?.[group.audience] ?? AUDIENCE_LABELS[group.audience] ?? group.audience}｜${group.seed}**：${group.terms.join("、") || "无返回"}`,
			);
		}
		lines.push("");
	}
	lines.push("## 本次搜索关键词", "");
	for (const query of pending.queries) lines.push(`- ${query.keyword}`);
	if (pending.errors.length) {
		lines.push("", "## 采集异常", "");
		for (const error of pending.errors)
			lines.push(`- ${error.stage}：${error.message}`);
	}
	lines.push("");
	return `${lines.join("\n")}\n`;
}

function calculateScore(scoreBreakdown) {
	return Math.round(
		Object.entries(SCORE_WEIGHTS).reduce(
			(sum, [key, weight]) => sum + scoreBreakdown[key] * weight,
			0,
		),
	);
}

function priorityForScore(score) {
	if (score >= 80) return "high";
	if (score >= 65) return "medium";
	return "low";
}

function escapeTable(value) {
	return String(value ?? "")
		.replace(/\|/g, "\\|")
		.replace(/\n/g, " ");
}
