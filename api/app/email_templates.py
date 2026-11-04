"""Branded HTML emails (with a plain-text twin) for every message the app sends.

Email clients ignore most modern CSS, so the layout is tables with inline styles, which render the same in Gmail, Outlook,
Apple Mail and phones. Colours match the website. Anything that came from a user or a database row is HTML-escaped.
"""

from dataclasses import dataclass
from html import escape

from app.config import get_settings

FOREST, LIME, INK, MUTED, LINE, GROUND = "#163a2c", "#c9f26c", "#10251d", "#56675e", "#dde3d6", "#f4f6ef"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


@dataclass(frozen=True)
class Message:
    subject: str
    text: str
    html: str


def absolute(url: str) -> str:
    """Links in an email must be full addresses: a path like /orders/1 means nothing inside an inbox."""
    if url.startswith(("http://", "https://")):
        return url
    return f"{get_settings().web_url.rstrip('/')}/{url.lstrip('/')}"


def _button(label: str, url: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px 0 8px 0"><tr>'
        f'<td style="background:{LIME};border-radius:999px">'
        f'<a href="{escape(url, quote=True)}" style="display:inline-block;padding:14px 28px;font-family:{FONT};font-size:16px;'
        f'font-weight:700;color:{FOREST};text-decoration:none;border-radius:999px">{escape(label)}</a>'
        f"</td></tr></table>"
    )


def _code_box(code: str) -> str:
    spaced = "&nbsp;".join(escape(ch) for ch in code)
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0 8px 0"><tr>'
        f'<td align="center" style="background:{GROUND};border:2px dashed {FOREST};border-radius:14px;padding:22px 12px">'
        f'<div style="font-family:SFMono-Regular,Menlo,Consolas,monospace;font-size:38px;line-height:1;font-weight:800;'
        f'letter-spacing:6px;color:{FOREST}">{spaced}</div></td></tr></table>'
    )


def _layout(title: str, preheader: str, inner: str) -> str:
    site = get_settings().web_url.rstrip("/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"><title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:{GROUND}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{GROUND}">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{GROUND}"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid {LINE};border-radius:18px;overflow:hidden">
<tr><td style="background:{FOREST};padding:22px 28px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:12px"><img src="{escape(site)}/icons/icon-192.png" width="40" height="40" alt="" style="display:block;border:0;border-radius:11px"></td>
<td style="font-family:{FONT};font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.3px">Campus <span style="color:{LIME}">Plug</span></td>
</tr></table></td></tr>
<tr><td style="padding:32px 28px 12px 28px;font-family:{FONT};color:{INK}">{inner}</td></tr>
<tr><td style="padding:8px 28px 28px 28px;font-family:{FONT};font-size:12px;line-height:18px;color:{MUTED}">
<div style="border-top:1px solid {LINE};padding-top:16px">You are receiving this because of activity on your Campus Plug account.
Campus Plug will never ask you for your password or a payment by email.<br>
<a href="{escape(site)}" style="color:{FOREST};font-weight:600">Open Campus Plug</a></div></td></tr>
</table></td></tr></table></body></html>"""


def _heading(text: str) -> str:
    return f'<h1 style="margin:0 0 12px 0;font-size:26px;line-height:32px;font-weight:800;color:{INK}">{escape(text)}</h1>'


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 12px 0;font-size:16px;line-height:25px;color:{MUTED}">{escape(text)}</p>'


def code_email(code: str, minutes: int = 10) -> Message:
    subject = "Your Campus Plug code"
    inner = (
        _heading("Confirm your email")
        + _paragraph("Use this code to finish signing up. Enter it on the Campus Plug page you have open.")
        + _code_box(code)
        + f'<p style="margin:12px 0 4px 0;font-size:14px;color:{MUTED}">The code expires in {minutes} minutes and works once.</p>'
        + f'<p style="margin:0 0 12px 0;font-size:14px;color:{MUTED}">Did not ask for this? You can ignore this email. Nobody can use your account without the code.</p>'
    )
    text = f"Your Campus Plug code is {code}. It expires in {minutes} minutes and works once. If you did not ask for it, ignore this email."
    return Message(subject, text, _layout(subject, f"Your code is {code}. It expires in {minutes} minutes.", inner))


def reset_email(link: str, minutes: int = 30) -> Message:
    subject = "Reset your Campus Plug password"
    inner = (
        _heading("Choose a new password")
        + _paragraph(
            "Someone, hopefully you, asked to reset the password for your Campus Plug account. Tap the button to choose a new one."
        )
        + _button("Reset my password", link)
        + f'<p style="margin:16px 0 4px 0;font-size:14px;color:{MUTED}">The link works for {minutes} minutes and only once.</p>'
        + f'<p style="margin:0 0 4px 0;font-size:14px;color:{MUTED}">Did not ask for this? Ignore this email and your password stays the same.</p>'
        + f'<p style="margin:16px 0 0 0;font-size:12px;line-height:18px;color:{MUTED};word-break:break-all">Button not working? Paste this address into your browser:<br>{escape(link)}</p>'
    )
    text = f"Use this link within {minutes} minutes to choose a new password: {link}\n\nIf you did not ask for this, ignore this email."
    return Message(subject, text, _layout(subject, "Choose a new password for your Campus Plug account.", inner))


def notification_email(title: str, body: str, url: str) -> Message:
    link = absolute(url)
    inner = _heading(title) + _paragraph(body) + _button("Open in Campus Plug", link)
    text = f"{body}\n\nOpen: {link}"
    return Message(title, text, _layout(title, body, inner))
