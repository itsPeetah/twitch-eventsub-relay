import http.server
import json
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser


class OAuthManager:
    def __init__(self, config):
        self.config = config
        self.token_file = "tokens.json"
        self.tokens = self.load_tokens()

    def load_tokens(self):
        try:
            with open(self.token_file, "r") as f:
                return json.load(f)
        except OSError:
            return None
        except json.JSONDecodeError:
            return None

    def save_tokens(self, tokens):
        self.tokens = tokens
        self.tokens["expires_at"] = time.time() + tokens["expires_in"]
        with open(self.token_file, "w") as f:
            json.dump(self.tokens, f)

    def get_token(self):
        if not self.tokens:
            self.authorize_manually()
        if time.time() > self.tokens.get("expires_at", 0) - 60:
            self.refresh_token()
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
