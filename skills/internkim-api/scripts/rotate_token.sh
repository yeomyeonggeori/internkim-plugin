#!/bin/sh
# Replace the stored token with a fresh one, without either passing through a
# terminal, a shell history, or an agent's conversation.

set -eu

SERVICE="internkim"
ACCOUNT="api"
BASE_URL="${INTERNKIM_API_URL:-https://api.intern.kim/v1}"
USER_AGENT="internkim-api-skill/1.0"

if command -v security >/dev/null 2>&1; then
	READ_TOKEN="security find-generic-password -s $SERVICE -a $ACCOUNT -w"
	STORE_TOKEN="security add-generic-password -U -s $SERVICE -a $ACCOUNT -w"
elif command -v secret-tool >/dev/null 2>&1; then
	READ_TOKEN="secret-tool lookup service $SERVICE account $ACCOUNT"
	STORE_TOKEN=""
else
	echo "no secret store found; rotate through the settings page instead" >&2
	exit 1
fi

OLD_TOKEN="$($READ_TOKEN)"
[ -n "$OLD_TOKEN" ] || { echo "nothing stored to rotate" >&2; exit 1; }

call() {
	curl -sS -X "$1" \
		-H "Authorization: Bearer $2" \
		-H "Content-Type: application/json" \
		-A "$USER_AGENT" \
		${4:+--data-binary "$4"} \
		"$BASE_URL$3"
}

OLD_NAME="${1:-}"
if [ -z "$OLD_NAME" ]; then
	echo "usage: rotate_token.sh <the name the stored token goes by>" >&2
	echo "the tokens this one can see:" >&2
	call GET "$OLD_TOKEN" /tokens "" |
		sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/  \1/p' >&2
	exit 1
fi

NEW_NAME="$OLD_NAME-$(date -u +%Y%m%dT%H%M%SZ)"

MINTED="$(call POST "$OLD_TOKEN" /token "{\"name\":\"$NEW_NAME\"}")"
NEW_TOKEN="$(printf '%s' "$MINTED" | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
case "$NEW_TOKEN" in
	ik_*) ;;
	*) echo "the API did not answer with a token: $MINTED" >&2; exit 1 ;;
esac

if ! call GET "$NEW_TOKEN" /tokens "" >/dev/null; then
	echo "the new token does not answer; the old one is untouched" >&2
	exit 1
fi

if [ -n "$STORE_TOKEN" ]; then
	$STORE_TOKEN "$NEW_TOKEN"
else
	printf '%s' "$NEW_TOKEN" | secret-tool store --label='internkim API token' service "$SERVICE" account "$ACCOUNT"
fi

REVOKED="$(call DELETE "$NEW_TOKEN" "/token?name=$OLD_NAME" "")"
case "$REVOKED" in
	*forgotten*) ;;
	*) echo "stored the new token, but the old one is still live: $REVOKED" >&2; exit 1 ;;
esac

echo "Rotated. The stored token is now called $NEW_NAME; $OLD_NAME is revoked." >&2
echo "Open a new shell so INTERNKIM_TOKEN picks it up." >&2
