import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# EMAIL PROVIDER SWITCH
# Set EMAIL_PROVIDER in environment to switch:
#   brevo     → Brevo API (default, recommended for production)
#   sendgrid  → SendGrid API
#   resend    → Resend API
#   mailgun   → Mailgun API
#   smtp      → Django SMTP (dev/fallback)
# ─────────────────────────────────────────────


def _build_otp_email(otp_code, purpose):
    subject_map = {
        "registration": f"Verify your AlumniAI account — OTP: {otp_code}",
        "login":        f"Your AlumniAI login OTP: {otp_code}",
        "verify":       f"Verify your email — OTP: {otp_code}",
    }
    subject = subject_map.get(purpose, f"Your AlumniAI OTP: {otp_code}")

    plain = f"""AlumniAI — Your OTP

OTP: {otp_code}

This OTP expires in 10 minutes.
Do not share this OTP with anyone.

— The AlumniAI Team"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
  .hdr{{background:#2563EB;padding:28px 32px;text-align:center}}
  .hdr h1{{color:#fff;margin:0;font-size:26px}}
  .bdy{{padding:32px}}
  .otp-box{{background:#EFF6FF;border:2px dashed #2563EB;border-radius:8px;padding:24px;text-align:center;margin:24px 0}}
  .otp-code{{font-size:42px;font-weight:700;color:#1D4ED8;letter-spacing:10px}}
  .warn{{background:#FFFBEB;border-left:4px solid #F59E0B;padding:14px 18px;border-radius:4px;margin-top:20px;font-size:14px;color:#92400E}}
  .ftr{{text-align:center;padding:20px;font-size:12px;color:#9CA3AF;border-top:1px solid #E5E7EB}}
</style></head>
<body>
  <div class="wrap">
    <div class="hdr"><h1>AlumniAI</h1></div>
    <div class="bdy">
      <p>Hello,</p>
      <p>Use the one-time password below to complete your request on <strong>AlumniAI</strong>.</p>
      <div class="otp-box"><div class="otp-code">{otp_code}</div></div>
      <p style="text-align:center;color:#6B7280;font-size:14px">Expires in <strong>10 minutes</strong>.</p>
      <div class="warn">&#9888; <strong>Do not share this OTP with anyone.</strong></div>
      <p style="margin-top:24px">If you did not request this, please ignore this email.</p>
      <p>— The AlumniAI Team</p>
    </div>
    <div class="ftr">&copy; 2026 AlumniAI. All rights reserved.</div>
  </div>
</body></html>"""

    return subject, plain, html


# ── Provider implementations ──────────────────────────────────

def _send_brevo(to_email, subject, html, plain):
    """Brevo (Sendinblue) API — https://app.brevo.com"""
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    sender_email = getattr(settings, 'EMAIL_SENDER', settings.DEFAULT_FROM_EMAIL)
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'AlumniAI')

    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        json={
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html,
            "textContent": plain,
        },
        headers={"api-key": api_key, "content-type": "application/json"},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise Exception(f"Brevo error {resp.status_code}: {resp.text}")
    logger.info(f"Brevo: sent to {to_email} — {resp.json().get('messageId')}")


def _send_sendgrid(to_email, subject, html, plain):
    """SendGrid API — https://sendgrid.com"""
    api_key = getattr(settings, 'SENDGRID_API_KEY', '')
    sender_email = getattr(settings, 'EMAIL_SENDER', settings.DEFAULT_FROM_EMAIL)
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'AlumniAI')

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": sender_email, "name": sender_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain},
                {"type": "text/html",  "value": html},
            ],
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if resp.status_code not in (200, 202):
        raise Exception(f"SendGrid error {resp.status_code}: {resp.text}")
    logger.info(f"SendGrid: sent to {to_email}")


def _send_resend(to_email, subject, html, plain):
    """Resend API — https://resend.com"""
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    sender_email = getattr(settings, 'EMAIL_SENDER', settings.DEFAULT_FROM_EMAIL)
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'AlumniAI')

    resp = requests.post(
        "https://api.resend.com/emails",
        json={
            "from": f"{sender_name} <{sender_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": plain,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise Exception(f"Resend error {resp.status_code}: {resp.text}")
    logger.info(f"Resend: sent to {to_email} — {resp.json().get('id')}")


def _send_mailgun(to_email, subject, html, plain):
    """Mailgun API — https://mailgun.com"""
    api_key = getattr(settings, 'MAILGUN_API_KEY', '')
    domain = getattr(settings, 'MAILGUN_DOMAIN', '')
    sender_email = getattr(settings, 'EMAIL_SENDER', settings.DEFAULT_FROM_EMAIL)
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'AlumniAI')

    resp = requests.post(
        f"https://api.mailgun.net/v3/{domain}/messages",
        auth=("api", api_key),
        data={
            "from": f"{sender_name} <{sender_email}>",
            "to": to_email,
            "subject": subject,
            "text": plain,
            "html": html,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise Exception(f"Mailgun error {resp.status_code}: {resp.text}")
    logger.info(f"Mailgun: sent to {to_email}")


def _send_smtp(to_email, subject, html, plain):
    """Django SMTP backend — for dev or fallback"""
    from django.core.mail import send_mail
    send_mail(
        subject=subject,
        message=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        html_message=html,
        fail_silently=False,
    )
    logger.info(f"SMTP: sent to {to_email}")


# ── Provider registry — add new providers here ────────────────
_PROVIDERS = {
    'brevo':     (_send_brevo,     'BREVO_API_KEY'),
    'sendgrid':  (_send_sendgrid,  'SENDGRID_API_KEY'),
    'resend':    (_send_resend,    'RESEND_API_KEY'),
    'mailgun':   (_send_mailgun,   'MAILGUN_API_KEY'),
    'smtp':      (_send_smtp,      None),
}


# ── Main function ─────────────────────────────────────────────

def send_otp_email(user_id, email, otp_code, purpose):
    """
    Send OTP email using the configured provider.

    Switch provider by setting EMAIL_PROVIDER env variable:
      brevo | sendgrid | resend | mailgun | smtp

    If EMAIL_PROVIDER is not set, auto-detects based on available API keys.
    """
    subject, plain, html = _build_otp_email(otp_code, purpose)
    logger.info(f"Sending OTP to {email} (user_id={user_id}, purpose={purpose})")

    # Get configured provider
    provider = getattr(settings, 'EMAIL_PROVIDER', '').lower().strip()

    # Auto-detect if not explicitly set
    if not provider:
        if getattr(settings, 'BREVO_API_KEY', ''):
            provider = 'brevo'
        elif getattr(settings, 'SENDGRID_API_KEY', ''):
            provider = 'sendgrid'
        elif getattr(settings, 'RESEND_API_KEY', ''):
            provider = 'resend'
        elif getattr(settings, 'MAILGUN_API_KEY', ''):
            provider = 'mailgun'
        else:
            provider = 'smtp'

    logger.info(f"Using email provider: {provider}")

    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unknown EMAIL_PROVIDER '{provider}'. "
            f"Valid options: {list(_PROVIDERS.keys())}"
        )

    send_fn, _ = _PROVIDERS[provider]
    send_fn(email, subject, html, plain)

    logger.info(f"OTP email sent successfully to {email} via {provider}")


# ── Celery task wrapper ───────────────────────────────────────

try:
    from celery import shared_task

    @shared_task(
        bind=True,
        max_retries=3,
        default_retry_delay=30,
        name='accounts.send_otp_email',
    )
    def send_otp_email_task(self, user_id, email, otp_code, purpose):
        try:
            send_otp_email(user_id, email, otp_code, purpose)
        except Exception as exc:
            logger.error(f"OTP email failed for {email}: {exc}")
            raise self.retry(exc=exc)

except ImportError:
    pass
