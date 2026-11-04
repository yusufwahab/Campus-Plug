"""Writes sample emails to api/email_previews/*.html so you can open them in a browser. Sends nothing.

Run from api/:  python scripts/preview_emails.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.email_templates import code_email, notification_email, reset_email  # noqa: E402

out = Path(__file__).resolve().parents[1] / "email_previews"
out.mkdir(exist_ok=True)
samples = {
    "code": code_email("688179"),
    "reset": reset_email("https://campusplug.example/reset-password?token=example-token"),
    "notification": notification_email(
        "Your order was accepted", "Kemi's Corner accepted order CP-O-1042. They will mark it ready soon.", "/orders/CP-O-1042"
    ),
}
for name, message in samples.items():
    (out / f"{name}.html").write_text(message.html, encoding="utf-8")
print("Open these in a browser:", *[str(out / f"{n}.html") for n in samples], sep="\n  ")
