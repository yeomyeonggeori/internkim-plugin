import { useEffect, useState } from "react";
import { resolveBlockComponent } from "./blocks";
import {
	fallbackContent,
	loadSiteContent,
	type Block,
	type NavigationItem,
	type SiteContent,
	type SitePage,
} from "./site-content";
import { AuthPage } from "./auth/AuthPage";
import { clearSession, refreshSession, useSession } from "./auth/session";

function blockAnchor(index: number): string {
	return `block-${index + 1}`;
}

function currentHashPath(): string {
	const hash = window.location.hash.replace(/^#/, "");
	return hash.startsWith("/") ? hash : "/";
}

function useHashPath(): string {
	const [path, setPath] = useState(currentHashPath());
	useEffect(() => {
		const handleHashChange = () => setPath(currentHashPath());
		window.addEventListener("hashchange", handleHashChange);
		return () => window.removeEventListener("hashchange", handleHashChange);
	}, []);
	return path;
}

function activePageFor(pages: SitePage[], path: string): SitePage {
	return pages.find((page) => page.path === path) ?? pages[0];
}

function anchorNavItemsFrom(blocks: Block[], siteName: string): NavigationItem[] {
	const seenTitles = new Set<string>();
	const navigationItems: NavigationItem[] = [];
	blocks.forEach((block, index) => {
		if (block.variant === "hero") return;
		if (!block.title || block.title === siteName) return;
		if (seenTitles.has(block.title)) return;
		seenTitles.add(block.title);
		navigationItems.push({ label: block.title, href: "#" + blockAnchor(index) });
	});
	return navigationItems;
}

function navigationItemsFrom(content: SiteContent): NavigationItem[] {
	if (content.navigationItems) return content.navigationItems;
	if (content.pages.length > 1) {
		return content.pages.map((page) => ({ label: page.title, href: "#" + page.path }));
	}
	return anchorNavItemsFrom(content.pages[0].blocks, content.siteName);
}

function App() {
	const [content, setContent] = useState<SiteContent>(fallbackContent);
	const path = useHashPath();
	const session = useSession();

	useEffect(() => {
		let isMounted = true;
		loadSiteContent().then((loadedContent) => {
			if (isMounted) setContent(loadedContent);
		});
		return () => {
			isMounted = false;
		};
	}, []);

	const auth = content.auth;
	useEffect(() => {
		if (content.auth) refreshSession(content.auth.userCollection);
	}, [content.auth]);
	const authMode = auth && path === auth.loginPath ? "login" : auth && auth.allowSignup && path === auth.signupPath ? "signup" : undefined;
	const page = activePageFor(content.pages, path);
	const requiresSession = auth !== undefined && page.access === "authenticated" && session === null;

	useEffect(() => {
		document.title = page.path === "/" ? content.siteName : `${page.title} — ${content.siteName}`;
		window.scrollTo(0, 0);
	}, [content.siteName, page]);

	const { siteName } = content;
	const navigationItems = navigationItemsFrom(content);

	return (
		<div className="min-h-screen bg-background text-foreground antialiased">
			<header className="site-header"><div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
				<a href="#/" className="font-semibold tracking-tight">
					{siteName}
				</a>
				<nav className="flex max-w-[60vw] items-center gap-5 overflow-x-auto whitespace-nowrap text-sm text-muted-foreground sm:max-w-none sm:gap-6">
					{navigationItems.map((navigationItem) => (
						<a
							key={navigationItem.href}
							href={navigationItem.href}
							className={
								"transition-colors hover:text-foreground" +
								(navigationItem.href === "#" + page.path && content.pages.length > 1
									? " font-semibold text-foreground"
									: "")
							}
						>
							{navigationItem.label}
						</a>
					))}
					{auth ? (
						session ? (
							<button
								type="button"
								onClick={() => clearSession()}
								className="transition-colors hover:text-foreground"
							>
								로그아웃
							</button>
						) : (
							<a href={"#" + auth.loginPath} className="transition-colors hover:text-foreground">
								로그인
							</a>
						)
					) : null}
				</nav>
				</div>
			</header>

			<main className="mx-auto max-w-4xl px-6">
				{authMode && auth ? (
					<AuthPage mode={authMode} auth={auth} />
				) : requiresSession && auth ? (
					<AuthPage mode="login" auth={auth} />
				) : (
					page.blocks.map((block, index) => {
						const BlockComponent = resolveBlockComponent(block.variant);
						return <BlockComponent key={page.path + blockAnchor(index)} block={block} anchorID={blockAnchor(index)} />;
					})
				)}
			</main>

			<footer className="border-t border-border">
				<div className="mx-auto flex max-w-4xl flex-col gap-4 px-6 py-12 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
					<span className="font-semibold text-foreground">{siteName}</span>
					<nav className="flex flex-wrap gap-4">
						{navigationItems.map((navigationItem) => (
							<a key={navigationItem.href} href={navigationItem.href} className="transition-colors hover:text-foreground">
								{navigationItem.label}
							</a>
						))}
					</nav>
				</div>
			</footer>
		</div>
	);
}

export default App;
