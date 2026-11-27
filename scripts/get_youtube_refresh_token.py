#!/usr/bin/env python3
"""One-time zero-dependency helper to mint a permanent YOUTUBE_REFRESH_TOKEN for GitHub Actions.

Usage:
    python3 scripts/get_youtube_refresh_token.py

Requirements:
  - Create a free Desktop/Web OAuth 2.0 Client in Google Cloud Console with YouTube Data API v3 enabled.
  - Add http://localhost:8765/callback as an Authorized Redirect URI (for Web app clients).
  - Run this script once on your machine, approve in your browser, and paste YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN into GitHub Repository Secrets.
"""

from __future__ import annotations

import http.server
import json
import sys
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://localhost:8765/callback"
SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
)


def main() -> int:
    print("=== FailSafe Lab — Gerador de YOUTUBE_REFRESH_TOKEN (100% Grátis) ===")
    client_id = input("Cole seu YOUTUBE_CLIENT_ID: ").strip()
    client_secret = input("Cole seu YOUTUBE_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        print("Erro: CLIENT_ID e CLIENT_SECRET são obrigatórios.")
        return 1

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
        }
    )

    captured: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                captured["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>Autorizado! Pode fechar esta aba e voltar ao terminal.</h2>")
            else:
                captured["error"] = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
    print("\nAbrindo navegador para autorizar seu canal do YouTube...")
    print(f"Se não abrir automaticamente, acesse:\n{auth_url}\n")
    webbrowser.open(auth_url)

    while "code" not in captured and "error" not in captured:
        server.handle_request()
    server.server_close()

    if "error" in captured:
        print(f"Autorização cancelada ou falhou: {captured['error']}")
        return 1

    body = urllib.parse.urlencode(
        {
            "code": captured["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        tokens = json.loads(resp.read().decode("utf-8"))

    refresh = tokens.get("refresh_token")
    if not refresh:
        print("Atenção: Google não retornou refresh_token. Revogue o app em myaccount.google.com/permissions e tente novamente.")
        return 2

    print("\n=== SUCESSO! Adicione estes 4 Secrets no GitHub (Settings -> Secrets -> Actions) ===")
    print("PUBLISH_PROVIDER      = direct")
    print(f"YOUTUBE_CLIENT_ID     = {client_id}")
    print(f"YOUTUBE_CLIENT_SECRET = {client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN = {refresh}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
