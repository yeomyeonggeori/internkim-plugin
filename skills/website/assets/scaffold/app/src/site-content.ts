export type BlockVariant = "hero" | "features" | "prose" | "cta" | "faq" | "contact";

export type BlockItem = {
	title: string;
	body: string;
	icon?: string;
};

export type Block = {
	variant: BlockVariant;
	title?: string;
	body?: string;
	items?: BlockItem[];
	actionLabel?: string;
	actionHref?: string;
	image?: string;
	imageAlt?: string;
	backdrop?: string;
};

export type SitePage = {
	path: string;
	title: string;
	blocks: Block[];
	access?: "public" | "authenticated";
};

export type SiteAuth = {
	enabled: boolean;
	userCollection: string;
	allowSignup: boolean;
	loginPath: string;
	signupPath: string;
	redirectAfterLogin: string;
	providers: string[];
};

export type NavigationItem = {
	label: string;
	href: string;
};

export type SiteContent = {
	siteName: string;
	tagline?: string;
	pages: SitePage[];
	navigationItems?: NavigationItem[];
	auth?: SiteAuth;
};

export const fallbackContent: SiteContent = {
	siteName: "__SITE_TITLE__",
	tagline: "이 사이트가 무엇에 대한 것인지 한 줄로 소개하세요.",
	pages: [
		{
			path: "/",
			title: "__SITE_TITLE__",
			blocks: [
				{
					variant: "hero",
					title: "__SITE_TITLE__",
					body: "이 사이트가 무엇에 대한 것인지 한 줄로 소개하세요.",
					actionLabel: "자세히 보기",
					actionHref: "#block-2",
				},
				{
					variant: "prose",
					title: "소개",
					body: "이 섹션에 요청에 맞는 소개 내용을 채워 주세요.",
				},
				{
					variant: "contact",
					title: "연락처",
					body: "이메일, 전화 등 연락 방법을 적어 주세요.",
				},
			],
		},
	],
};

const knownBlockVariants: readonly string[] = ["hero", "features", "prose", "cta", "faq", "contact"];

function isBlockVariant(value: unknown): value is BlockVariant {
	return typeof value === "string" && knownBlockVariants.includes(value);
}

function isNonEmptyString(value: unknown): value is string {
	return typeof value === "string" && value.length > 0;
}

function isOptionalString(value: unknown): value is string | undefined {
	return value === undefined || typeof value === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

type LegacySiteSection = {
	title: string;
	body: string;
};

function parseLegacySiteSection(value: unknown): LegacySiteSection | undefined {
	if (!isRecord(value)) return undefined;
	if (!isNonEmptyString(value.title) || !isNonEmptyString(value.body)) return undefined;
	return { title: value.title, body: value.body };
}

function parseBlockItem(value: unknown): BlockItem | undefined {
	if (!isRecord(value)) return undefined;
	if (!isNonEmptyString(value.title) || !isNonEmptyString(value.body)) return undefined;
	return { title: value.title, body: value.body, icon: isNonEmptyString(value.icon) ? value.icon : undefined };
}

function parseBlockItems(value: unknown): BlockItem[] | undefined {
	if (!Array.isArray(value)) return undefined;
	const items = value.map(parseBlockItem).filter((item): item is BlockItem => item !== undefined);
	return items.length > 0 ? items : undefined;
}

function parseBlock(value: unknown): Block | undefined {
	if (!isRecord(value)) return undefined;
	if (!isBlockVariant(value.variant)) return undefined;
	if (!isOptionalString(value.title) || !isOptionalString(value.body)) return undefined;
	if (!isOptionalString(value.actionLabel) || !isOptionalString(value.actionHref)) return undefined;
	return {
		variant: value.variant,
		title: value.title,
		body: value.body,
		items: parseBlockItems(value.items),
		actionLabel: value.actionLabel,
		actionHref: value.actionHref,
		image: isNonEmptyString(value.image) ? value.image : undefined,
		imageAlt: isNonEmptyString(value.imageAlt) ? value.imageAlt : undefined,
		backdrop: isNonEmptyString(value.backdrop) ? value.backdrop : undefined,
	};
}

function parseBlocks(value: unknown[]): Block[] {
	return value.map(parseBlock).filter((block): block is Block => block !== undefined);
}

function normalizeLegacySections(value: Record<string, unknown>): Block[] {
	const siteName = value.siteName;
	const tagline = value.tagline;
	const heroActionLabel = value.heroActionLabel;
	const heroActionHref = value.heroActionHref;
	const legacySections = Array.isArray(value.sections)
		? value.sections.map(parseLegacySiteSection).filter((section): section is LegacySiteSection => section !== undefined)
		: [];
	const heroBlock: Block = {
		variant: "hero",
		title: isNonEmptyString(siteName) ? siteName : undefined,
		body: isOptionalString(tagline) ? tagline : undefined,
		actionLabel: isOptionalString(heroActionLabel) ? heroActionLabel : undefined,
		actionHref: isOptionalString(heroActionHref) ? heroActionHref : undefined,
	};
	const proseBlocks: Block[] = legacySections.map((section) => ({
		variant: "prose",
		title: section.title,
		body: section.body,
	}));
	return [heroBlock, ...proseBlocks];
}

function normalizePagePath(value: unknown): string | undefined {
	if (!isNonEmptyString(value)) return undefined;
	if (!value.startsWith("/")) return undefined;
	return value.length > 1 && value.endsWith("/") ? value.slice(0, -1) : value;
}

function parsePage(value: unknown): SitePage | undefined {
	if (!isRecord(value)) return undefined;
	const path = normalizePagePath(value.path);
	if (path === undefined) return undefined;
	if (!isNonEmptyString(value.title)) return undefined;
	if (!Array.isArray(value.blocks)) return undefined;
	const blocks = parseBlocks(value.blocks);
	if (blocks.length === 0) return undefined;
	const access = value.access === "authenticated" ? "authenticated" : undefined;
	return { path, title: value.title, blocks, access };
}

function parsePages(value: unknown): SitePage[] {
	if (!Array.isArray(value)) return [];
	return value.map(parsePage).filter((page): page is SitePage => page !== undefined);
}

function parseNavigationItems(value: unknown): NavigationItem[] | undefined {
	if (!isRecord(value) || !Array.isArray(value.items)) return undefined;
	const items = value.items.flatMap((item) => {
		if (!isRecord(item)) return [];
		if (!isNonEmptyString(item.label) || !isNonEmptyString(item.href)) return [];
		return [{ label: item.label, href: item.href }];
	});
	return items.length > 0 ? items : undefined;
}

function pagesFrom(value: Record<string, unknown>): SitePage[] {
	const pages = parsePages(value.pages);
	if (pages.length > 0) return pages;
	const blocks = Array.isArray(value.blocks) ? parseBlocks(value.blocks) : normalizeLegacySections(value);
	if (blocks.length === 0) return [];
	const title = isNonEmptyString(value.siteName) ? value.siteName : "홈";
	return [{ path: "/", title, blocks }];
}

function parseAuth(value: unknown): SiteAuth | undefined {
	if (!isRecord(value) || value.enabled !== true) return undefined;
	const pathOr = (candidate: unknown, fallback: string) =>
		isNonEmptyString(candidate) && candidate.startsWith("/") ? candidate : fallback;
	const providers = Array.isArray(value.providers)
		? value.providers.filter(isNonEmptyString).map((provider) => provider.trim().toLowerCase())
		: [];
	return {
		enabled: true,
		userCollection: isNonEmptyString(value.userCollection) ? value.userCollection : "users",
		allowSignup: value.allowSignup !== false,
		loginPath: pathOr(value.loginPath, "/login"),
		signupPath: pathOr(value.signupPath, "/signup"),
		redirectAfterLogin: pathOr(value.redirectAfterLogin, "/"),
		providers,
	};
}

function parseSiteContent(value: unknown): SiteContent | undefined {
	if (!isRecord(value)) return undefined;
	if (!isNonEmptyString(value.siteName)) return undefined;
	if (!isOptionalString(value.tagline)) return undefined;
	const pages = pagesFrom(value);
	if (pages.length === 0) return undefined;
	return {
		siteName: value.siteName,
		tagline: value.tagline,
		pages,
		navigationItems: parseNavigationItems(value.navigation),
		auth: parseAuth(value.auth),
	};
}

export async function loadSiteContent(): Promise<SiteContent> {
	try {
		const response = await fetch("./site-content.json");
		if (!response.ok) return fallbackContent;
		const parsedJSON: unknown = await response.json();
		return parseSiteContent(parsedJSON) ?? fallbackContent;
	} catch {
		return fallbackContent;
	}
}
