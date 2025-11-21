import os
import smtplib
from mcp.server.fastmcp import FastMCP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("notification_server")

@mcp.tool()
def draft_email(recipient: str, subject: str, body: str) -> str:
    """Creates a draft email for review."""
    return f"""
    [DRAFT]
    To: {recipient}
    Subject: {subject}
    Body: {body}
    """

@mcp.tool()
def send_email(recipient: str, subject: str, body: str) -> str:
    """Sends the email via SMTP."""
    smtp_server = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SMTP_USER")
    sender_password = os.getenv("SMTP_PASSWORD")

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return f"Email sent to {recipient}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")