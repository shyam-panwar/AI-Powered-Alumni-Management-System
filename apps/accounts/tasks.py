# import logging
# from django.core.mail import send_mail
# from django.conf import settings

# logger = logging.getLogger(__name__)


# def _build_otp_email(otp_code, purpose):
#     subject_map = {
#         'registration': f'Verify your AlumniAI account — OTP: {otp_code}',
#         'login':        f'Your AlumniAI login OTP: {otp_code}',
#         'verify':       f'Verify your email — OTP: {otp_code}',
#     }
#     subject = subject_map.get(purpose, f'Your AlumniAI OTP: {otp_code}')

#     plain = (
#         f"AlumniAI — Your OTP\n\n"
#         f"OTP: {otp_code}\n\n"
#         f"This OTP expires in 10 minutes.\n"
#         f"Do not share this OTP with anyone.\n\n"
#         f"— The AlumniAI Team"
#     )

#     html = f"""<!DOCTYPE html>
# <html lang="en">
# <head><meta charset="UTF-8">
# <style>
#   body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
#   .wrap{{max-width:560px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
#   .hdr{{background:#2563EB;padding:28px 32px;text-align:center}}
#   .hdr h1{{color:#fff;margin:0;font-size:26px}}
#   .bdy{{padding:32px}}
#   .otp-box{{background:#EFF6FF;border:2px dashed #2563EB;border-radius:8px;padding:24px;text-align:center;margin:24px 0}}
#   .otp-code{{font-size:42px;font-weight:700;color:#1D4ED8;letter-spacing:10px}}
#   .warn{{background:#FFFBEB;border-left:4px solid #F59E0B;padding:14px 18px;border-radius:4px;margin-top:20px;font-size:14px;color:#92400E}}
#   .ftr{{text-align:center;padding:20px;font-size:12px;color:#9CA3AF;border-top:1px solid #E5E7EB}}
# </style></head>
# <body>
#   <div class="wrap">
#     <div class="hdr"><h1>AlumniAI</h1></div>
#     <div class="bdy">
#       <p>Hello,</p>
#       <p>Use the one-time password below to complete your request on <strong>AlumniAI</strong>.</p>
#       <div class="otp-box"><div class="otp-code">{otp_code}</div></div>
#       <p style="text-align:center;color:#6B7280;font-size:14px">This OTP expires in <strong>10 minutes</strong>.</p>
#       <div class="warn">⚠️ <strong>Do not share this OTP with anyone.</strong> AlumniAI staff will never ask for your OTP.</div>
#       <p style="margin-top:24px">If you did not request this, please ignore this email.</p>
#       <p>— The AlumniAI Team</p>
#     </div>
#     <div class="ftr">&copy; 2026 AlumniAI. All rights reserved.</div>
#   </div>
# </body></html>"""

#     return subject, plain, html


# def send_otp_email(user_id, email, otp_code, purpose):
#     """
#     Send OTP email. Called directly in dev (console backend prints to terminal).
#     Wrapped as a Celery task in production via send_otp_email_task.
#     """
#     subject, plain, html = _build_otp_email(otp_code, purpose)
#     try:
#         send_mail(
#             subject=subject,
#             message=plain,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=[email],
#             html_message=html,
#             fail_silently=False,
#         )
#         logger.info(f"OTP email sent to {email} (user_id={user_id}, purpose={purpose})")
#     except Exception as exc:
#         logger.error(f"Failed to send OTP email to {email}: {exc}")


# # Celery task wrapper — only used when broker is available
# try:
#     from celery import shared_task

#     @shared_task(bind=True, max_retries=3, default_retry_delay=30, name='accounts.send_otp_email')
#     def send_otp_email_task(self, user_id, email, otp_code, purpose):
#         try:
#             send_otp_email(user_id, email, otp_code, purpose)
#         except Exception as exc:
#             raise self.retry(exc=exc)

# except ImportError:
#     pass





import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_otp_email(otp_code, purpose):
    subject_map = {
        'registration': f'Verify your AlumniAI account — OTP: {otp_code}',
        'login':        f'Your AlumniAI login OTP: {otp_code}',
        'verify':       f'Verify your email — OTP: {otp_code}',
    }
    subject = subject_map.get(purpose, f'Your AlumniAI OTP: {otp_code}')

    plain = (
        f"AlumniAI — Your OTP\n\n"
        f"OTP: {otp_code}\n\n"
        f"This OTP expires in 10 minutes.\n"
        f"Do not share this OTP with anyone.\n\n"
        f"— The AlumniAI Team"
    )

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
      <p style="text-align:center;color:#6B7280;font-size:14px">This OTP expires in <strong>10 minutes</strong>.</p>
      <div class="warn">⚠️ <strong>Do not share this OTP with anyone.</strong> AlumniAI staff will never ask for your OTP.</div>
      <p style="margin-top:24px">If you did not request this, please ignore this email.</p>
      <p>— The AlumniAI Team</p>
    </div>
    <div class="ftr">&copy; 2026 AlumniAI. All rights reserved.</div>
  </div>
</body></html>"""

    return subject, plain, html


def send_otp_email(user_id, email, otp_code, purpose):
    """
    Send OTP email. Called directly in dev (console backend prints to terminal).
    Wrapped as a Celery task in production via send_otp_email_task.
    """
    subject, plain, html = _build_otp_email(otp_code, purpose)
    try:
        send_mail(
            subject=subject,
            message=plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f"OTP email sent to {email} (user_id={user_id}, purpose={purpose})")
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {email}: {exc}")


# Celery task wrapper — only used when broker is available
try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=30, name='accounts.send_otp_email')
    def send_otp_email_task(self, user_id, email, otp_code, purpose):
        try:
            send_otp_email(user_id, email, otp_code, purpose)
        except Exception as exc:
            raise self.retry(exc=exc)

except ImportError:
    pass
