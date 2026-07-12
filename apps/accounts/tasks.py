import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_otp_email(otp_code, purpose):
    subject_map = {
        "registration": f"Verify your AlumniAI account — OTP: {otp_code}",
        "login":        f"Your AlumniAI login OTP: {otp_code}",
        "verify":       f"Verify your email — OTP: {otp_code}",
    }
    subject = subject_map.get(purpose, f"Your AlumniAI OTP: {otp_code}")

    plain = f"AlumniAI OTP: {otp_code}\n\nExpires in 10 minutes. Do not share."

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0">
  <div style="max-width:560px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">
    <div style="background:#2563EB;padding:28px 32px;text-align:center">
      <h1 style="color:#fff;margin:0;font-size:26px">AlumniAI</h1>
    </div>
    <div style="padding:32px">
      <p>Hello,</p>
      <p>Use the one-time password below to complete your request on <strong>AlumniAI</strong>.</p>
      <div style="background:#EFF6FF;border:2px dashed #2563EB;border-radius:8px;padding:24px;text-align:center;margin:24px 0">
        <div style="font-size:42px;font-weight:700;color:#1D4ED8;letter-spacing:10px">{otp_code}</div>
      </div>
      <p style="text-align:center;color:#6B7280;font-size:14px">Expires in <strong>10 minutes</strong>.</p>
      <p style="margin-top:20px;font-size:14px;color:#92400E;background:#FFFBEB;border-left:4px solid #F59E0B;padding:14px 18px;border-radius:4px">
        <strong>Do not share this OTP with anyone.</strong>
      </p>
      <p style="margin-top:24px">If you did not request this, please ignore this email.</p>
      <p>— The AlumniAI Team</p>
    </div>
    <div style="text-align:center;padding:20px;font-size:12px;color:#9CA3AF;border-top:1px solid #E5E7EB">
      &copy; 2026 AlumniAI. All rights reserved.
    </div>
  </div>
</body></html>"""

    return subject, plain, html


def send_otp_email(user_id, email, otp_code, purpose):
    """Send OTP via Brevo HTTP API only."""
    subject, plain, html = _build_otp_email(otp_code, purpose)

    api_key = getattr(settings, 'BREVO_API_KEY', '')
    sender_email = getattr(settings, 'EMAIL_SENDER', getattr(settings, 'DEFAULT_FROM_EMAIL', ''))
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'AlumniAI')

    if not api_key:
        raise ValueError("BREVO_API_KEY is not configured.")
    if not sender_email:
        raise ValueError("EMAIL_SENDER is not configured.")

    logger.info(f"[OTP] Sending to {email} | user_id={user_id} | purpose={purpose}")

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        json={
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": email}],
            "subject": subject,
            "htmlContent": html,
            "textContent": plain,
        },
        headers={
            "api-key": api_key,
            "content-type": "application/json",
            "accept": "application/json",
        },
        timeout=15,
    )

    if response.status_code not in (200, 201):
        raise Exception(f"Brevo API error {response.status_code}: {response.text}")

    message_id = response.json().get("messageId", "")
    logger.info(f"[OTP] Sent successfully to {email} | messageId={message_id}")


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
            logger.error(f"[OTP] Task failed for {email}: {exc}")
            raise self.retry(exc=exc)

except ImportError:
    pass
