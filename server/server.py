"""
KAngel Piano — MidiShow Proxy Server
Securely holds midishow credentials and proxies search/download requests.
Deploy to Render / Railway / Fly.io free tier.
"""

import os

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from midishow import MidiShowClient

app = Flask(__name__)
CORS(app)

MS_USER = os.environ.get("MIDISHOW_USER", "")
MS_PASS = os.environ.get("MIDISHOW_PASS", "")

client = MidiShowClient(MS_USER, MS_PASS) if MS_USER and MS_PASS else None


def _ensure_client():
    if not client:
        return False
    if not client.is_logged_in:
        client.login()
    return client.is_logged_in


@app.route("/api/health")
def health():
    if not client:
        return jsonify({"status": "error", "message": "No credentials configured"}), 503
    logged_in = _ensure_client()
    return jsonify({"status": "ok" if logged_in else "login_failed", "logged_in": logged_in})


@app.route("/api/search")
def search():
    if not _ensure_client():
        return jsonify({"error": "MidiShow login failed"}), 503

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    page = int(request.args.get("page", 1))
    sort = request.args.get("sort", "default")

    result = client.search(q, page, sort)
    return jsonify(result)


@app.route("/api/download")
def download():
    if not _ensure_client():
        return jsonify({"error": "MidiShow login failed"}), 503

    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing parameter 'url'"}), 400

    fname, data = client.download(url)
    if fname is None:
        return jsonify({"error": data}), 400

    return Response(
        data,
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "X-Filename": fname,
        },
    )


if __name__ == "__main__":
    if not MS_USER or not MS_PASS:
        print("WARNING: Set MIDISHOW_USER and MIDISHOW_PASS environment variables")
    else:
        print(f"MidiShow proxy starting with user: {MS_USER}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
