import test from "node:test";
import assert from "node:assert/strict";
import { PassThrough } from "node:stream";
import { readHiddenLine } from "../lib/hidden-input.mjs";

test("interactive credential input is hidden and returned to the caller", async () => {
	const input = new PassThrough();
	input.isTTY = true;
	input.isRaw = false;
	input.setRawMode = (value) => {
		input.isRaw = value;
	};
	const output = new PassThrough();
	let visible = "";
	output.on("data", (chunk) => {
		visible += chunk.toString();
	});

	const pending = readHiddenLine({ input, output, prompt: "TikHub API Key: " });
	input.write("test-token-1234567890\n");
	const value = await pending;

	assert.equal(value, "test-token-1234567890");
	assert.match(visible, /TikHub API Key:/);
	assert.doesNotMatch(visible, /test-token-1234567890/);
});
