import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRun, openDatabase } from "../lib/database.mjs";
import { finalizeReport } from "../lib/report.mjs";

const audiences = [
	...Array(4).fill("student"),
	...Array(3).fill("high_tech_enterprise"),
	...Array(3).fill("hangzhou_e_talent"),
];

test("finalizes an exact, quota-balanced, evidence-backed report", async () => {
	const workspace = await mkdtemp(join(tmpdir(), "topic-radar-"));
	await mkdir(join(workspace, "data", "pending"), { recursive: true });
	const runId = "2026-07-28-test";
	const sourceUrl = "https://www.xiaohongshu.com/explore/note-1?xsec_token=abc";
	const pending = {
		runId,
		runDate: "2026-07-28",
		startedAt: new Date().toISOString(),
		provider: "tikhub",
		lookbackDays: 7,
		requestCount: 10,
		estimatedCostUsd: 0.1,
		stats: { uniqueNotes: 10, commentNotes: 5, suggestionTerms: 3 },
		errors: [],
		searchSuggestions: [
			{ audience: "student", seed: "软著", terms: ["软著申请流程"] },
			{
				audience: "high_tech_enterprise",
				seed: "高企软著",
				terms: ["高企知识产权"],
			},
			{
				audience: "hangzhou_e_talent",
				seed: "杭州E类人才",
				terms: ["杭州人才认定"],
			},
		],
		queries: [{ keyword: "大学生软著" }],
		evidence: [{ noteUrl: sourceUrl }],
	};
	await writeFile(
		join(workspace, "data", "pending", `${runId}.json`),
		JSON.stringify(pending),
	);
	const db = openDatabase(workspace);
	createRun(db, {
		runId,
		runDate: pending.runDate,
		status: "awaiting_finalize",
		startedAt: pending.startedAt,
	});
	db.close();

	const topics = audiences.map((audience, index) => {
		const score = 80 - index;
		return {
			audience,
			title: `测试选题标题 ${index + 1}`,
			whyNow: "近期相关讨论和用户问题集中出现，需要及时回应。",
			userQuestion: "这项业务应该如何判断和准备？",
			targetScenario: "用户准备材料并比较办理路径时",
			angle: "基于证据说明核验步骤，不作结果承诺。",
			contentGap: "现有样本缺少逐项核验材料真实性的操作清单。",
			evidenceSummary: "样本笔记与评论共同显示用户集中关注准备步骤和判断标准。",
			titleAlternatives: [`备选标题甲 ${index + 1}`, `备选标题乙 ${index + 1}`],
			contentFormat: "6页图文清单",
			contentStructure: "tutorial",
			titlePattern: "question",
			writingFramework: "tutorial-stepbystep",
			hook: "先别急着提交，这三项材料最容易准备错。",
			mustCover: ["材料核验", "办理步骤"],
			outline: ["说明适用场景", "拆解准备步骤", "给出官方核验入口"],
			callToAction: "收藏清单并先核验所在地当前规则。",
			demandKeywords: [
				audience === "student"
					? "软著"
					: audience === "high_tech_enterprise"
						? "高企软著"
						: "杭州E类人才",
			],
			priority: score >= 80 ? "high" : score >= 65 ? "medium" : "low",
			difficulty: "medium",
			scoreBreakdown: {
				demandFit: score,
				evidenceStrength: score,
				timingFit: score,
				differentiation: score,
				executability: score,
				riskSafety: score,
			},
			score,
			riskNote: "发布前必须核验当前有效的官方政策文件。",
			doNotSay: ["不得承诺一定通过或一定获得资格"],
			sourceUrls: [sourceUrl],
		};
	});

	const result = await finalizeReport({ workspace, runId, topics });
	const markdown = await readFile(result.reportPath, "utf8");
	assert.equal(result.summary.requestCount, 10);
	assert.equal(result.summary.estimatedCostUsd, 0.1);
	assert.equal(result.summary.evidenceCount, 1);
	assert.equal(result.summary.collectionErrorCount, 0);
	assert.equal(result.summary.priorityCounts.high, 1);
	assert.deepEqual(
		result.summary.topTopics.map((topic) => topic.title),
		["测试选题标题 1", "测试选题标题 2", "测试选题标题 3"],
	);
	assert.match(markdown, /小红书每日选题日报/);
	assert.match(markdown, /10\. 测试选题标题 10/);
	assert.match(markdown, /今日决策摘要/);
	assert.match(markdown, /评分拆解.*需求匹配/);
	assert.match(markdown, /写作框架.*教程步骤型/);
	assert.match(markdown, /禁止表述/);
	assert.match(markdown, /xsec_token=abc/);
});
