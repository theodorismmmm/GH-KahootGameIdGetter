"""
Kahoot Game ID Getter — Web Interface
Flask application that exposes a simple UI for looking up Kahoot game info.
"""

from __future__ import annotations

import sys
import os

# Allow importing get_game_id from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify

from get_game_id import get_game_info, _collect_session_info, _FIELD_LABELS

import re

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/lookup", methods=["POST"])
def lookup():
    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", "")).strip()

    if not re.fullmatch(r"\d{4,10}", pin):
        return jsonify({"error": "Invalid PIN — must be 4–10 digits."}), 400

    try:
        game_id, api_data = get_game_info(pin)
    except SystemExit:
        return jsonify({"error": "No active game found for that PIN, or the Kahoot API is unreachable."}), 404

    info = _collect_session_info(pin, game_id, api_data)

    # Build a labelled list for the frontend
    priority = ["live_game_id", "pin"]
    ordered_keys = priority + sorted(k for k in info if k not in priority)

    rows = [
        {"key": k, "label": _FIELD_LABELS.get(k, k.replace("_", " ").title()), "value": info[k]}
        for k in ordered_keys
    ]

    return jsonify({"game_id": game_id, "rows": rows})


if __name__ == "__main__":
    app.run(debug=True)
