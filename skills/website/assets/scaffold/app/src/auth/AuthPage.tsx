import { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import type { SiteAuth } from "../site-content";
import { passkeyLogin, passkeySignUp, signIn, signInWithProvider, signUp, supportsPasskey, useSession } from "./session";

type AuthPageProps = {
	mode: "login" | "signup";
	auth: SiteAuth;
};

export function AuthPage({ mode, auth }: AuthPageProps) {
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [message, setMessage] = useState("");
	const [isBusy, setIsBusy] = useState(false);
	const session = useSession();
	const isSignup = mode === "signup";

	useEffect(() => {
		if (session) window.location.hash = auth.redirectAfterLogin;
	}, [session, auth.redirectAfterLogin]);

	const continueWithProvider = async (provider: string) => {
		setIsBusy(true);
		setMessage("");
		const result = await signInWithProvider(auth.userCollection, provider);
		setIsBusy(false);
		if (!result.ok) {
			setMessage(result.message);
			return;
		}
		window.location.hash = auth.redirectAfterLogin;
	};

	const continueWithPasskey = async () => {
		if (!username) {
			setMessage("아이디를 먼저 입력해 주세요.");
			return;
		}
		setIsBusy(true);
		setMessage("");
		const result = isSignup
			? await passkeySignUp(auth.userCollection, username).catch((error: Error) => ({ ok: false as const, message: error.message }))
			: await passkeyLogin(auth.userCollection, username).catch((error: Error) => ({ ok: false as const, message: error.message }));
		setIsBusy(false);
		if (!result.ok) {
			setMessage(result.message);
			return;
		}
		window.location.hash = auth.redirectAfterLogin;
	};

	const submit = async (event: React.FormEvent) => {
		event.preventDefault();
		setIsBusy(true);
		setMessage("");
		const result = isSignup
			? await signUp(auth.userCollection, username, password)
			: await signIn(auth.userCollection, username, password);
		setIsBusy(false);
		if (!result.ok) {
			setMessage(result.message);
			return;
		}
		window.location.hash = auth.redirectAfterLogin;
	};

	return (
		<section className="mx-auto flex min-h-[60vh] max-w-sm flex-col justify-center py-20">
			<h1 className="text-3xl font-bold tracking-tight">{isSignup ? "회원가입" : "로그인"}</h1>
			<form onSubmit={submit} className="mt-8 flex flex-col gap-4">
				<div className="flex flex-col gap-1.5">
					<Label htmlFor="auth-username">아이디</Label>
					<Input
						id="auth-username"
						autoComplete="username"
						value={username}
						onChange={(event) => setUsername(event.target.value)}
						required
					/>
				</div>
				<div className="flex flex-col gap-1.5">
					<Label htmlFor="auth-password">비밀번호</Label>
					<Input
						id="auth-password"
						type="password"
						autoComplete={isSignup ? "new-password" : "current-password"}
						minLength={8}
						value={password}
						onChange={(event) => setPassword(event.target.value)}
						required
					/>
				</div>
				{message ? <p className="text-sm text-destructive">{message}</p> : null}
				<Button type="submit" disabled={isBusy} className="mt-2">
					{isBusy ? "처리 중..." : isSignup ? "가입하기" : "로그인"}
				</Button>
				{supportsPasskey() ? (
					<Button type="button" variant="outline" disabled={isBusy} onClick={continueWithPasskey}>
						{isSignup ? "패스키로 가입" : "패스키로 로그인"}
					</Button>
				) : null}
				{auth.providers.map((provider) => (
					<Button key={provider} type="button" variant="outline" disabled={isBusy} onClick={() => continueWithProvider(provider)}>
						{provider} 계정으로 계속
					</Button>
				))}
			</form>
			<p className="mt-6 text-sm text-muted-foreground">
				{isSignup ? (
					<>이미 계정이 있나요? <a className="font-medium underline underline-offset-4" href={"#" + auth.loginPath}>로그인</a></>
				) : auth.allowSignup ? (
					<>계정이 없나요? <a className="font-medium underline underline-offset-4" href={"#" + auth.signupPath}>회원가입</a></>
				) : null}
			</p>
		</section>
	);
}
