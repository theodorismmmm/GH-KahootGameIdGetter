"""
Kahoot Game ID Getter
Given a Kahoot PIN, retrieves the internal game/quiz UUID by querying
the Kahoot session API — the same endpoint a host's browser calls.
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import base64

import requests


KAHOOT_SESSION_URL = "https://kahoot.it/reserve/session/{}/?{}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://kahoot.it",
    "Referer": "https://kahoot.it/",
}

UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _try_decode_token(token: str) -> dict:
    """Attempt to base64-decode the session token and parse it as JSON."""
    for variant in (token, token + "=", token + "=="):
        for decoder in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                raw = decoder(variant)
                return json.loads(raw.decode("utf-8"))
            except Exception:
                continue
    return {}


def _solve_challenge(challenge: str) -> str | None:
    """
    Solve the JavaScript challenge returned by the Kahoot session API.

    The challenge is a JS snippet of the form:
        setTimeout(function(){
            var nonce = "...";
            var answer = nonce.split("").map(function(char, position){
                return String.fromCharCode(char.charCodeAt(0) + (position % N));
            }).join("");
            return answer;
        }, 0)

    We replicate the transformation in Python to produce the same answer.
    """
    nonce_match = re.search(r'var\s+\w+\s*=\s*["\']([^"\']+)["\']', challenge)
    if not nonce_match:
        return None
    nonce = nonce_match.group(1)

    mod_match = re.search(r"position\s*%\s*(\d+)", challenge)
    mod = int(mod_match.group(1)) if mod_match else 5

    return "".join(chr(ord(c) + (i % mod)) for i, c in enumerate(nonce))


def _xor_decode(token: str, challenge_answer: str) -> str:
    """XOR the raw session token with the challenge answer to get the WS token."""
    # Add padding incrementally until decoding succeeds
    decoded_token = b""
    for padding in ("", "=", "=="):
        try:
            decoded_token = base64.b64decode(token + padding)
            break
        except Exception:
            continue
    answer_bytes = challenge_answer.encode("utf-8")
    result = bytes(a ^ answer_bytes[i % len(answer_bytes)] for i, a in enumerate(decoded_token))
    return result.decode("utf-8", errors="replace")


def get_game_id(pin: str) -> str:
    """
    Retrieve the Kahoot game (quiz) UUID for the given PIN.

    Returns the UUID string, or raises SystemExit on failure.
    """
    timestamp = int(time.time() * 1000)
    url = KAHOOT_SESSION_URL.format(pin, timestamp)

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as exc:
        print(f"[ERROR] Request failed: {exc}")
        sys.exit(1)

    if response.status_code == 404:
        print(f"[ERROR] No active game found for PIN: {pin}")
        print("Make sure the game has been started by the host before running this tool.")
        sys.exit(1)

    if response.status_code != 200:
        print(f"[ERROR] Unexpected HTTP {response.status_code} from Kahoot API")
        print(response.text[:500])
        sys.exit(1)

    session_token = response.headers.get("X-Kahoot-Session-Token", "")

    try:
        data = response.json()
    except ValueError:
        print("[ERROR] Kahoot API returned non-JSON response")
        print(response.text[:500])
        sys.exit(1)

    game_id = None

    # ── Method 1: Look for game ID fields in the JSON body ────────────────
    # Check top-level fields first (modern Kahoot API returns liveGameId here)
    for field in ("liveGameId", "uuid", "quizId", "gameId", "kahootId"):
        if data.get(field):
            game_id = str(data[field])
            break

    # Also check nested under "kahoot" key (older API format)
    if not game_id and "kahoot" in data and isinstance(data["kahoot"], dict):
        game_id = (
            data["kahoot"].get("uuid")
            or data["kahoot"].get("quizId")
            or data["kahoot"].get("gameId")
        )

    # ── Method 2: Decode the session token (base64 JSON) ─────────────────
    if not game_id and session_token:
        token_data = _try_decode_token(session_token)
        game_id = (
            token_data.get("uuid")
            or token_data.get("quizId")
            or token_data.get("gameId")
            or token_data.get("kahootId")
        )

    # ── Method 3: Solve challenge → XOR-decode token → scan for UUID ─────
    if not game_id and session_token and "challenge" in data:
        challenge_answer = _solve_challenge(data["challenge"])
        if challenge_answer:
            decoded = _xor_decode(session_token, challenge_answer)
            uuids = UUID_PATTERN.findall(decoded)
            if uuids:
                game_id = uuids[0]

    # ── Method 4: Regex scan the entire raw response ─────────────────────
    if not game_id:
        uuids = UUID_PATTERN.findall(response.text)
        if uuids:
            game_id = uuids[0]

    if not game_id:
        print("[ERROR] Could not extract the game ID from the Kahoot API response.")
        print(f"Response fields available: {list(data.keys())}")
        print(f"Session token present: {bool(session_token)}")
        sys.exit(1)

    return game_id


def write_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT (GitHub Actions output file)."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"{key}={value}\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python get_game_id.py <kahoot-pin>")
        sys.exit(1)

    pin = sys.argv[1].strip()

    if not re.fullmatch(r"\d{4,10}", pin):
        print(f"[ERROR] '{pin}' does not look like a valid Kahoot PIN (4–10 digits).")
        sys.exit(1)

    print(f"Looking up game ID for PIN: {pin} ...")
    game_id = get_game_id(pin)

    print(f"\n✅ Game ID: {game_id}")
    write_github_output("game_id", game_id)


if __name__ == "__main__":
    main()
