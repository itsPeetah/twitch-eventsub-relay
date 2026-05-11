import http.server
import json
import logging
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser


class OAuthManager:
    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.token_file = "tokens.json"
        self.tokens = self.load_tokens()

    def load_tokens(self):
        try:
            with open(self.token_file, "r") as f:
                tokens = json.load(f)
                self.logger.debug("loaded tokens from %s", self.token_file)
                return tokens
        except OSError:
            self.logger.debug("no token file %s (yet)", self.token_file)
            return None
        except json.JSONDecodeError:
            self.logger.debug("token file %s is invalid JSON", self.token_file)
            return None

    def save_tokens(self, tokens):
        self.tokens = tokens
        self.tokens["expires_at"] = time.time() + tokens["expires_in"]
        with open(self.token_file, "w") as f:
            json.dump(self.tokens, f)
        self.logger.debug(
            "saved tokens expires_at=%s (in %.0fs)",
            self.tokens["expires_at"],
            self.tokens["expires_at"] - time.time(),
        )

    def get_token(self):
        if not self.tokens:
            self.logger.debug("get_token: starting interactive authorize")
            self.authorize_manually()
        exp = self.tokens.get("expires_at", 0)
        now = time.time()
        if now > exp - 60:
            self.logger.debug(
                "get_token: refreshing (now=%.0f expires_at=%.0f)",
                now,
                exp,
            )
            self.refresh_token()
        else:
            self.logger.debug(
                "get_token: using cached access token (expires_at=%.0f)",
                exp,
            )
        return self.tokens["access_token"]

    def authorize_manually(self):
        state = secrets.token_hex(16)
        params = {
            "client_id": self.config["client_id"],
            "redirect_uri": "http://localhost:8080",
            "response_type": "code",
            "scope": " ".join(self.config["scopes"]),
            "state": state,
        }
        url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode(params)
        self.logger.debug("authorize scopes=%s", self.config.get("scopes"))
        print("[*] Opening browser for authorization...")
        webbrowser.open(url)

        code = None

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal code
                query = urllib.parse.urlparse(self.path).query
                code = urllib.parse.parse_qs(query).get("code", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorized! You can close this tab.")

        httpd = http.server.HTTPServer(("localhost", 8080), Handler)
        while not code:
            httpd.handle_request()
        httpd.server_close()
        self.exchange_code(code)

    def exchange_code(self, code):
        data = urllib.parse.urlencode(
            {
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:8080",
            }
        ).encode()
        req = urllib.request.Request(
            "https://id.twitch.tv/oauth2/token", data=data, method="POST"
        )
        with urllib.request.urlopen(req) as f:
            self.save_tokens(json.loads(f.read().decode()))
        self.logger.debug("exchange_code: token exchange succeeded")

    def refresh_token(self):
        print("[*] Refreshing access token...")
        data = urllib.parse.urlencode(
            {
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": self.tokens["refresh_token"],
            }
        ).encode()
        req = urllib.request.Request(
            "https://id.twitch.tv/oauth2/token", data=data, method="POST"
        )
        with urllib.request.urlopen(req) as f:
            self.save_tokens(json.loads(f.read().decode()))
        self.logger.debug("refresh_token: succeeded")
