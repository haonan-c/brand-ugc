import { createInterface } from "node:readline/promises";
import { Writable } from "node:stream";

class MutedOutput extends Writable {
	constructor(destination) {
		super();
		this.destination = destination;
		this.muted = false;
	}

	_write(chunk, encoding, callback) {
		if (!this.muted) this.destination.write(chunk, encoding);
		callback();
	}
}

export async function readHiddenLine({
	input = process.stdin,
	output = process.stderr,
	prompt = "Secret: ",
} = {}) {
	if (!input.isTTY) {
		throw new Error("Hidden input requires an interactive terminal.");
	}
	const mutedOutput = new MutedOutput(output);
	const readline = createInterface({ input, output: mutedOutput, terminal: true });
	output.write(prompt);
	mutedOutput.muted = true;
	try {
		return (await readline.question("")).trim();
	} finally {
		mutedOutput.muted = false;
		readline.close();
		output.write("\n");
	}
}
