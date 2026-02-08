import smtplib
import os
from email.message import EmailMessage

def send_verification_otp(to_email, otp):
    msg = EmailMessage()
    msg["Subject"] = "TrustPoll – Verify your email"
    msg["From"] = os.getenv("SMTP_EMAIL")
    msg["To"] = to_email

    msg.set_content(f"""
Hello,

Your TrustPoll verification code is:

{otp}

This code is valid for 10 minutes.
If you did not request this, please ignore this email.

– TrustPoll Team
""")

    server = smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")))
    server.starttls()
    server.login(
        os.getenv("SMTP_EMAIL"),
        os.getenv("SMTP_PASSWORD")
    )
    server.send_message(msg)
    server.quit()
