"""Optional SMTP delivery with PDF and text attachments."""
from __future__ import annotations
import smtplib
import ssl
import os
import mimetypes
from email.message import EmailMessage
from pathlib import Path


def send_report(cfg: dict, subject_line: str, body_text: str, attachments) -> dict:
    """Send one attachment path or a list of attachment paths."""
    if not cfg.get("enabled"):
        return {"sent": False, "reason": "email disabled in configuration"}
    host = cfg.get("smtp_host")
    port = int(cfg.get("smtp_port", 587))
    user = cfg.get("smtp_user", "")
    pwd = cfg.get("smtp_password", "")
    sender = cfg.get("from_addr") or user
    to = cfg.get("to_addr")
    if not (host and to and sender):
        return {"sent": False, "reason": "incomplete SMTP configuration (host/from/to)"}

    msg = EmailMessage()
    msg["Subject"] = subject_line
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body_text)

    # Normaliser : accepter str ou liste
    if isinstance(attachments, str):
        attachments = [attachments]
    attachments = attachments or []

    for path in attachments:
        if not path or not os.path.exists(path):
            continue
        data = Path(path).read_bytes()
        ctype, _ = mimetypes.guess_type(path)
        if not ctype:
            ctype = "application/octet-stream"
        maintype, _, subtype = ctype.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                if user and pwd:
                    s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                if cfg.get("use_tls", True):
                    s.starttls(context=ssl.create_default_context())
                if user and pwd:
                    s.login(user, pwd)
                s.send_message(msg)
        return {"sent": True, "to": to, "attachments": [os.path.basename(p) for p in attachments]}
    except Exception as e:
        return {"sent": False, "reason": f"SMTP error: {e}"}
