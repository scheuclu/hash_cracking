"""Send status emails via the Gmail API."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDS_FILE = Path("./token.json")
RECIPIENT = "<todo>@gmail.com"
SENDER = "<todo>@gmail.com"


def get_creds() -> Credentials:
    return Credentials.from_authorized_user_file(str(CREDS_FILE), SCOPES)


def _build_message(content: str) -> dict[str, str]:
    message = EmailMessage()
    message.set_content(content)
    message["To"] = RECIPIENT
    message["From"] = SENDER
    message["Subject"] = " "
    return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}


def _message_from_file(filepath: Path | str) -> dict[str, str]:
    return _build_message(Path(filepath).read_text())


def _send(body: dict[str, str]) -> None:
    service = build("gmail", "v1", credentials=get_creds())
    sent = service.users().messages().send(userId="me", body=body).execute()
    print(f"Message Id: {sent['id']}")


def send_string_via_mail(content: str) -> None:
    _send(_build_message(content))


def send_file_via_mail(filepath: Path | str) -> None:
    _send(_message_from_file(filepath))


def main() -> None:
    send_string_via_mail("This is a test.")


if __name__ == "__main__":
    main()
