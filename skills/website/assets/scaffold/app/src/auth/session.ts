import PocketBase, { type AuthRecord } from "pocketbase";
import { useEffect, useState } from "react";

export const pocketbaseClient = new PocketBase("/");
pocketbaseClient.autoCancellation(false);

export type SessionUser = {
	id: string;
	username: string;
};

type SessionState = {
	token: string;
	user: SessionUser;
};

function toSessionUser(record: AuthRecord): SessionUser | null {
	if (!record) return null;
	return { id: record.id, username: String(record.username ?? "") };
}

export function currentSession(): SessionState | null {
	const user = toSessionUser(pocketbaseClient.authStore.record);
	if (!pocketbaseClient.authStore.isValid || !user) return null;
	return { token: pocketbaseClient.authStore.token, user };
}

export function clearSession() {
	pocketbaseClient.authStore.clear();
}

export function useSession(): SessionState | null {
	const [session, setSession] = useState<SessionState | null>(currentSession());
	useEffect(() => {
		return pocketbaseClient.authStore.onChange(() => setSession(currentSession()));
	}, []);
	return session;
}

type AuthResult = { ok: true } | { ok: false; message: string };

function firstErrorMessage(error: unknown, fallback: string): string {
	const response = (error as { response?: { data?: Record<string, { message?: string }>; message?: string } }).response;
	const fieldMessages = response?.data ? Object.values(response.data).map((entry) => entry?.message ?? "").filter(Boolean) : [];
	return fieldMessages[0] ?? response?.message ?? fallback;
}

export async function signIn(userCollection: string, username: string, password: string): Promise<AuthResult> {
	try {
		await pocketbaseClient.collection(userCollection).authWithPassword(username, password);
		return { ok: true };
	} catch (error) {
		return { ok: false, message: firstErrorMessage(error, "로그인에 실패했습니다. 아이디와 비밀번호를 확인해 주세요.") };
	}
}

export async function signUp(userCollection: string, username: string, password: string): Promise<AuthResult> {
	try {
		await pocketbaseClient.collection(userCollection).create({ username, password, passwordConfirm: password });
	} catch (error) {
		return { ok: false, message: firstErrorMessage(error, "가입에 실패했습니다.") };
	}
	return signIn(userCollection, username, password);
}

export async function signInWithProvider(userCollection: string, provider: string): Promise<AuthResult> {
	try {
		await pocketbaseClient.collection(userCollection).authWithOAuth2({ provider });
		return { ok: true };
	} catch (error) {
		return { ok: false, message: firstErrorMessage(error, provider + " 로그인이 아직 설정되지 않았습니다. 관리자에게 문의해 주세요.") };
	}
}

export async function refreshSession(userCollection: string): Promise<void> {
	if (!pocketbaseClient.authStore.isValid) return;
	try {
		await pocketbaseClient.collection(userCollection).authRefresh();
	} catch {
		pocketbaseClient.authStore.clear();
	}
}

function base64urlToBuffer(text: string): ArrayBuffer {
	const padded = text.replace(/-/g, "+").replace(/_/g, "/");
	const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
	return Uint8Array.from(raw, (character) => character.charCodeAt(0)).buffer;
}

function bufferToBase64url(buffer: ArrayBuffer): string {
	return btoa(String.fromCharCode(...new Uint8Array(buffer)))
		.replace(/\+/g, "-")
		.replace(/\//g, "_")
		.replace(/=+$/, "");
}

export function supportsPasskey(): boolean {
	return typeof window !== "undefined" && !!window.PublicKeyCredential;
}

async function postJSON(path: string, body: unknown): Promise<{ ok: boolean; payload: Record<string, unknown> }> {
	const response = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	const payload = await response.json().catch(() => ({}));
	return { ok: response.ok, payload };
}

function storeAuthPayload(payload: Record<string, unknown>) {
	pocketbaseClient.authStore.save(String(payload.token), payload.record as AuthRecord);
}

export async function passkeySignUp(userCollection: string, username: string): Promise<AuthResult> {
	void userCollection;
	const optionsResponse = await postJSON("/api/site-auth/passkey/register-options", { username });
	if (!optionsResponse.ok) return { ok: false, message: String(optionsResponse.payload.message ?? "패스키 등록 준비에 실패했습니다.") };
	const publicKey = optionsResponse.payload.publicKey as Record<string, unknown>;
	publicKey.challenge = base64urlToBuffer(String(publicKey.challenge));
	(publicKey.user as Record<string, unknown>).id = base64urlToBuffer(String((publicKey.user as Record<string, unknown>).id));
	const credential = (await navigator.credentials.create({ publicKey: publicKey as unknown as PublicKeyCredentialCreationOptions })) as PublicKeyCredential;
	const attestation = credential.response as AuthenticatorAttestationResponse;
	const verifyResponse = await postJSON("/api/site-auth/passkey/register", {
		username,
		credential: {
			id: credential.id,
			response: {
				clientDataJSON: bufferToBase64url(attestation.clientDataJSON),
				attestationObject: bufferToBase64url(attestation.attestationObject),
			},
		},
	});
	if (!verifyResponse.ok) return { ok: false, message: String(verifyResponse.payload.message ?? "패스키 등록에 실패했습니다.") };
	storeAuthPayload(verifyResponse.payload);
	return { ok: true };
}

export async function passkeyLogin(userCollection: string, username: string): Promise<AuthResult> {
	void userCollection;
	const optionsResponse = await postJSON("/api/site-auth/passkey/login-options", { username });
	if (!optionsResponse.ok) return { ok: false, message: String(optionsResponse.payload.message ?? "패스키 로그인 준비에 실패했습니다.") };
	const publicKey = optionsResponse.payload.publicKey as Record<string, unknown>;
	publicKey.challenge = base64urlToBuffer(String(publicKey.challenge));
	publicKey.allowCredentials = ((publicKey.allowCredentials as Array<Record<string, unknown>>) ?? []).map((entry) => ({
		...entry,
		id: base64urlToBuffer(String(entry.id)),
	}));
	const credential = (await navigator.credentials.get({ publicKey: publicKey as unknown as PublicKeyCredentialRequestOptions })) as PublicKeyCredential;
	const assertion = credential.response as AuthenticatorAssertionResponse;
	const verifyResponse = await postJSON("/api/site-auth/passkey/login", {
		username,
		credential: {
			id: credential.id,
			response: {
				clientDataJSON: bufferToBase64url(assertion.clientDataJSON),
				authenticatorData: bufferToBase64url(assertion.authenticatorData),
				signature: bufferToBase64url(assertion.signature),
			},
		},
	});
	if (!verifyResponse.ok) return { ok: false, message: String(verifyResponse.payload.message ?? "패스키 로그인에 실패했습니다.") };
	storeAuthPayload(verifyResponse.payload);
	return { ok: true };
}
