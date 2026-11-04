import httpx

from app.adapters import email as email_module
from app.adapters.email import BrevoEmail, LocalEmail
from app.email_templates import absolute, code_email, notification_email, reset_email

API = "/api/v1"


def test_code_email_shows_the_code_big_and_in_plain_text_too():
    m = code_email("688179")
    assert "6&nbsp;8&nbsp;8&nbsp;1&nbsp;7&nbsp;9" in m.html and "#c9f26c" in m.html and "#163a2c" in m.html
    assert "expires in 10 minutes" in m.html
    assert "688179" in m.text and "<" not in m.text
    assert m.subject == "Your Campus Plug code"
    assert "688179" in m.html.split("</div>", 1)[0]  # the code is also in the hidden preview line shown in the inbox list


def test_reset_email_has_a_button_and_a_pasteable_link():
    link = "https://campusplug.example/reset-password?token=abc.def"
    m = reset_email(link)
    assert f'href="{link}"' in m.html and "Reset my password" in m.html
    assert link in m.text and link in m.html.split("Button not working?")[1]


def test_notification_links_are_made_absolute_and_user_text_is_escaped():
    m = notification_email('<script>alert(1)</script> & "quotes"', "<img src=x onerror=alert(1)>", "/orders/CP-O-1")
    assert "<script>" not in m.html and "<img src=x" not in m.html
    assert "&lt;script&gt;" in m.html and "&lt;img src=x" in m.html
    assert 'href="http://localhost:3000/orders/CP-O-1"' in m.html
    assert "http://localhost:3000/orders/CP-O-1" in m.text
    assert absolute("https://other.example/x") == "https://other.example/x"


def test_a_link_with_quotes_cannot_break_out_of_the_href():
    m = reset_email('https://x.example/?a="><script>alert(1)</script>')
    assert "<script>" not in m.html


def test_brevo_sends_the_html_version_alongside_the_text(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(json)
        return httpx.Response(201, json={"messageId": "x"})

    monkeypatch.setattr(email_module.httpx, "post", fake_post)
    m = code_email("123456")
    BrevoEmail("k", "no-reply@campusplug.example", "Campus Plug").send("a@example.com", m.subject, m.text, m.html)
    assert seen["textContent"] == m.text and seen["htmlContent"] == m.html


def test_signup_and_reset_emails_use_the_branded_layout(client):
    LocalEmail.outbox.clear()
    LocalEmail.html_outbox.clear()
    client.post(
        f"{API}/auth/signup", json={"email": "ada@example.com", "password": "password123", "full_name": "Ada Obi", "phone": "08031234567"}
    )
    code_html = LocalEmail.html_outbox[-1]
    assert "Confirm your email" in code_html and "Campus" in code_html
    client.post(f"{API}/auth/forgot", json={"email": "ada@example.com"})
    assert "Reset my password" in LocalEmail.html_outbox[-1]
