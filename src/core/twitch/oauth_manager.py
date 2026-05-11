import http.server
import json
import logging
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from .app_config import TwitchAppConfig
from .token_database import OAuthTokenDatabase


class OAuthManager:
    """App-access token OAuth (browser redirect + callback server) and optional SQLite token store."""

    def __init__(
        self,
        config: TwitchAppConfig,
        logger: logging.Logger,
        token_db: str | Path | None = None,
    ):
        self.config = config
        self.logger = logger
        db_path = Path(token_db) if token_db is not None else Path("tokens.sqlite")
        self._tokens_db = OAuthTokenDatabase(db_path)
        self.tokens = self._tokens_db.load()
        if self.tokens:
            self.logger.debug("loaded tokens from %s", self._tokens_db.path)
        else:
            self.logger.debug("no token database %s (yet)", self._tokens_db.path)

    def oauth_redirect_uri(self) -> str:
        return self.config.oauth_redirect_uri

    def _oauth_redirect_listen_port(self) -> int:
        u = urllib.parse.urlparse(self.oauth_redirect_uri())
        if u.port is not None:
            return u.port
        if u.scheme == "https":
            return 443
        return 80

    def _oauth_listen_bind_host_port(self) -> tuple[str, int]:
        override = self.config.oauth_callback_listen_host
        port = self._oauth_redirect_listen_port()
        if override:
            return override.strip(), port
        u = urllib.parse.urlparse(self.oauth_redirect_uri())
        host = u.hostname or "localhost"
        return host, port

    def save_tokens(self, tokens):
        self.tokens = self._tokens_db.save(dict(tokens))
        self.logger.debug(
            "saved tokens expires_at=%s (in %.0fs)",
            self.tokens["expires_at"],
            self.tokens["expires_at"] - time.time(),
        )

    def _clear_token_store(self) -> None:
        self.tokens = None
        self._tokens_db.clear()

    def _scopes_requested(self) -> frozenset[str]:
        return frozenset(self.config.scopes)

    def _scopes_granted_in_file(self) -> frozenset[str] | None:
        if not self.tokens or "scope" not in self.tokens:
            return None
        raw = self.tokens["scope"]
        if isinstance(raw, list):
            return frozenset(raw)
        return frozenset(str(raw).split())

    def get_token(self):
        if self.tokens:
            granted = self._scopes_granted_in_file()
            if granted is None:
                self.logger.info(
                    "cached token has no scope metadata; re-authorizing against config"
                )
                self._clear_token_store()
            elif granted != self._scopes_requested():
                self.logger.info(
                    "OAuth scopes in config changed; discarding cached token and re-authorizing"
                )
                self._clear_token_store()

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
        redirect_uri = self.oauth_redirect_uri()
        state = secrets.token_hex(16)
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
        }
        url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode(params)
        self.logger.debug("authorize scopes=%s", list(self.config.scopes))
        print("[*] Authorize URL (open in a browser if it did not open automatically):")
        print(url)
        print("[*] Opening browser for authorization...")
        webbrowser.open(url)

        code = None
        oauth_error: tuple[str, str] | None = None
        log = self.logger

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                pass

            def do_GET(self):
                nonlocal code, oauth_error
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                qs = urllib.parse.parse_qs(parsed.query)
                err_list = qs.get("error")
                if err_list:
                    oauth_error = (
                        err_list[0],
                        qs.get("error_description", [""])[0],
                    )
                    log.error(
                        "OAuth callback error=%s description=%s",
                        oauth_error[0],
                        urllib.parse.unquote_plus(oauth_error[1]),
                    )
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(
                        f"Twitch OAuth error: {oauth_error[0]}".encode()
                    )
                    return
                code = qs.get("code", [None])[0]
                if code:
                    log.info(
                        "OAuth redirect received on %s (authorization code chars=%s)",
                        parsed.path or "/",
                        len(code),
                    )
                else:
                    log.warning(
                        "OAuth callback GET without code (path=%s); waiting for redirect with ?code=",
                        self.path,
                    )
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorized! You can close this tab.")

        bind_host, bind_port = self._oauth_listen_bind_host_port()
        httpd = http.server.HTTPServer((bind_host, bind_port), Handler)
        log.info(
            "Listening on http://%s:%s for OAuth redirect_uri=%s",
            bind_host,
            bind_port,
            redirect_uri,
        )
        while code is None and oauth_error is None:
            httpd.handle_request()
        httpd.server_close()
        if oauth_error:
            raise RuntimeError(
                f"OAuth failed: {oauth_error[0]} — "
                f"{urllib.parse.unquote_plus(oauth_error[1])}"
            )
        log.info("Stopping OAuth callback server; exchanging authorization code for tokens")
        self.exchange_code(code)

    def exchange_code(self, code):
        data = urllib.parse.urlencode(
            {
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.oauth_redirect_uri(),
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
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
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
