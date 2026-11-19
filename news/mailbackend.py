"""Sends email through Brevo's web API (HTTPS, port 443).

Render's free plan blocks normal email (SMTP) connections, but web requests
are allowed, so the site sends its newsletter this way."""
import json
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.core.mail.backends.base import BaseEmailBackend

API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoAPIBackend(BaseEmailBackend):
    def __init__(self, *args, api_key="", **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = (api_key or "").strip()

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            name, address = parseaddr(message.from_email)
            payload = {
                "sender": {"email": address, **({"name": name} if name else {})},
                "to": [{"email": to} for to in message.to],
                "subject": message.subject,
                "textContent": message.body,
            }
            for content, mimetype in getattr(message, "alternatives", []):
                if mimetype == "text/html":
                    payload["htmlContent"] = content
            headers = dict(getattr(message, "extra_headers", {}) or {})
            if headers:
                payload["headers"] = headers
            request = urllib.request.Request(
                API_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"api-key": self.api_key, "accept": "application/json",
                         "content-type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=20):
                    sent += 1
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                if not self._fail_silently:
                    raise RuntimeError(f"Brevo refused the email (HTTP {exc.code}): {detail}") from exc
        return sent
