import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from app.core.config import settings

async def send_email_with_attachment(to_email: str, subject: str, body: str, pdf_bytes: bytes, filename: str):
    """Send an email with a PDF attachment asynchronously."""
    message = MIMEMultipart()
    message["From"] = settings.EMAIL_SENDER
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    message.attach(attachment)

    try:
        await aiosmtplib.send(
            message,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=settings.EMAIL_SENDER,
            password=settings.EMAIL_PASSWORD,
        )
        print(f"[Email] Sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[Email Error] {e}")
        return False
