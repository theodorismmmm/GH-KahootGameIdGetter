# GH-KahootGameIdGetter

A tool that takes a **Kahoot PIN** and retrieves the internal **game (quiz) UUID** by querying
the Kahoot session API — the same request a host's browser makes when starting a game.

---

## How it works

1. A host starts a Kahoot game and shares the **PIN** (the 4–10 digit code players type to join).
2. Kahoot generates a session by calling `https://kahoot.it/reserve/session/<pin>/`.
3. This workflow hits that endpoint from GitHub Actions, extracts the game UUID from the
   response, and prints it in the run log.

The UUID is the internal identifier of the quiz on Kahoot's servers (e.g.
`a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

---

## Usage

### Via GitHub Actions (recommended)

1. Go to the **Actions** tab of this repository.
2. Select **"Get Kahoot Game ID"** from the workflow list.
3. Click **"Run workflow"**, enter the Kahoot PIN, and click **"Run workflow"** again.
4. Once the run completes, open it to see the Game ID printed in the **"Print Game ID"** step.

> **Note:** The Kahoot game must be **actively running** (the host has started it and it is
> waiting for players) when you trigger the workflow. PINs for games that have ended or not yet
> started will return a 404.

### Locally

```bash
pip install requests
python get_game_id.py <pin>
```

Example:

```
$ python get_game_id.py 1234567
Looking up game ID for PIN: 1234567 ...

✅ Game ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Files

| File | Description |
|------|-------------|
| `get_game_id.py` | Python script – queries the Kahoot session API and extracts the game UUID |
| `.github/workflows/get-kahoot-game-id.yml` | GitHub Actions workflow – runs the script via `workflow_dispatch` |
