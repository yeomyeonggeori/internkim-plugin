import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";

type Command = {
	name: string;
	arguments: string[];
};

type QualityIssue = {
	severity: "blocking" | "warning";
	category: string;
	target: string;
	message: string;
	suggestedFix: string;
};

const canonicalRuntimePATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin";

async function runCommand(command: Command): Promise<void> {
	const commandProcess = Bun.spawn([command.name, ...command.arguments], {
		env: { ...Bun.env, PATH: canonicalRuntimePATH },
		stdout: "inherit",
		stderr: "inherit",
	});
	const exitCode = await commandProcess.exited;
	if (exitCode !== 0) {
		throw new Error(command.name + " " + command.arguments.join(" ") + " failed with exit code " + exitCode);
	}
}

function readSource(path: string): string {
	if (!existsSync(path)) return "";
	return readFileSync(path, "utf8");
}

function sourceContainsAny(source: string, values: string[]): boolean {
	return values.some((value) => source.includes(value));
}

function collectDesignQualityIssues(): QualityIssue[] {
	const source = readSource("../DESIGN.md");
	const issueMessages: string[] = [];
	if (!source.startsWith("---\n")) {
		issueMessages.push("DESIGN.md must start with YAML front matter");
		return issueMessages.map(createDesignQualityIssue);
	}
	const frontMatterEnd = source.indexOf("\n---", 4);
	if (frontMatterEnd < 0) {
		issueMessages.push("DESIGN.md front matter must end with ---");
		return issueMessages.map(createDesignQualityIssue);
	}
	const frontMatter = source.slice(4, frontMatterEnd);
	for (const key of ["colors", "typography", "rounded", "spacing", "components"]) {
		if (!new RegExp("^" + key + "\\s*:", "m").test(frontMatter)) {
			issueMessages.push("DESIGN.md front matter is missing " + key);
		}
	}
	const body = source.slice(frontMatterEnd + 4);
	let previousIndex = -1;
	for (const section of ["Overview", "Colors", "Typography", "Layout", "Elevation & Depth", "Shapes", "Components", "Do's and Don'ts"]) {
		const sectionIndex = body.indexOf("## " + section);
		if (sectionIndex < 0) {
			issueMessages.push("DESIGN.md body is missing section: " + section);
			continue;
		}
		if (sectionIndex < previousIndex) {
			issueMessages.push("DESIGN.md section order is wrong at: " + section);
		}
		previousIndex = sectionIndex;
	}
	return issueMessages.map(createDesignQualityIssue);
}

function createDesignQualityIssue(message: string): QualityIssue {
	return {
		severity: "warning",
		category: "designDocument",
		target: "../DESIGN.md",
		message,
		suggestedFix: "Rewrite DESIGN.md using the canonical Stitch front matter and required section order.",
	};
}

function collectQualityIssues(): QualityIssue[] {
	const appSource = readSource("src/App.tsx");
	const styleSource = readSource("src/index.css");
	const issues: QualityIssue[] = [];
	const contentPath = "public/site-content.json";
	if (!existsSync(contentPath)) {
		issues.push({
			severity: "blocking",
			category: "contentModel",
			target: contentPath,
			message: "Create domain-specific site content before building the site.",
			suggestedFix: "Write realistic domain content to public/site-content.json matching the SiteContent schema.",
		});
	} else {
		try {
			JSON.parse(readSource(contentPath));
		} catch {
			issues.push({
				severity: "blocking",
				category: "contentModel",
				target: contentPath,
				message: "public/site-content.json must be valid JSON.",
				suggestedFix: "Fix the JSON syntax in public/site-content.json so it matches the SiteContent schema.",
			});
		}
	}
	if (sourceContainsAny(appSource + styleSource, [
		"INTERNKIM_SITE_STARTER_REPLACE_ME",
		"internkim React prototype",
		"Beautiful default scaffold",
		"Replace this starter",
		"workflowItems",
	])) {
		issues.push({
			severity: "blocking",
			category: "templateSmell",
			target: "src/App.tsx",
			message: "Replace the scaffold starter instead of editing its copy or card-grid structure.",
			suggestedFix: "Replace starter sections with a domain-specific first screen, real content structure, and non-generic UI flow.",
		});
	}
	return issues;
}

function writeBuildQuality(issues: QualityIssue[]): void {
	mkdirSync("../.internkim", { recursive: true });
	writeFileSync("../.internkim/build-quality.json", JSON.stringify({
		generatedAt: new Date().toISOString(),
		blockingIssueCount: issues.filter((issue) => issue.severity === "blocking").length,
		issues,
	}, null, 2) + "\n");
}

async function buildVite(): Promise<void> {
	const slowBuildDiagnostic = setTimeout(reportGuestProcessState, 45_000);
	await runCommand({ name: "bun", arguments: ["--bun", "./node_modules/vite/bin/vite.js", "build", "--logLevel", "info"] });
	clearTimeout(slowBuildDiagnostic);
}

function reportGuestProcessState(): void {
	logBuildStage("vite still running after 45s; guest process state follows");
	logBuildStage("BUN_INSTALL_CACHE_DIR=" + (Bun.env.BUN_INSTALL_CACHE_DIR ?? "(unset)"));
	logBuildStage("loadavg " + readSource("/proc/loadavg").trim());
	logBuildStage("meminfo " + readSource("/proc/meminfo").split("\n").slice(0, 3).join(" | "));
	for (const entry of readdirSync("/proc")) {
		if (!/^[0-9]+$/.test(entry)) continue;
		const stat = readSource(`/proc/${entry}/stat`);
		if (stat === "") continue;
		const fields = stat.split(" ");
		const utime = Number(fields[13]) + Number(fields[14]);
		if (utime < 100) continue;
		logBuildStage(`pid ${entry} comm ${fields[1]} state ${fields[2]} cpuTicks ${utime} cmdline ${readSource(`/proc/${entry}/cmdline`).replaceAll("\0", " ").slice(0, 120)}`);
	}
}

function logBuildStage(stage: string): void {
	console.error(`[build.ts ${new Date().toISOString()}] ${stage}`);
}

logBuildStage("start");
const qualityIssues = [...collectDesignQualityIssues(), ...collectQualityIssues()];
writeBuildQuality(qualityIssues);
logBuildStage("quality written");

if (!existsSync("node_modules/vite/bin/vite.js")) {
	logBuildStage("install starting");
	await runCommand({ name: "bun", arguments: ["install", "--prefer-offline"] });
	logBuildStage("install finished");
}
logBuildStage("vite build starting");
await buildVite();
logBuildStage("vite build finished");
writeBuildQuality(qualityIssues);
