"""
Email composition + send tools for the Notification agent.

Safety properties:
- HTML-escapes everything before injecting it into the HTML variant.
- Validates recipient against EMAIL_ALLOWED_DOMAINS / EMAIL_ALLOWED_RECIPIENTS.
- Returns the HTML variant alongside the plain-text draft instead of stashing
  it in os.environ (the previous side-channel).
"""

from __future__ import annotations

import html
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple

from shared.logging_utils import get_logger

logger = get_logger("agents.notification.email_draft")

_VERB_PREFIXES = [
    "summarize", "provide", "draft", "compose", "check", "get", "give", "share",
    "list", "show", "generate", "create", "prepare",
]

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _refine_purpose(raw: str) -> str:
    if not raw:
        return raw
    cleaned = raw.strip().lower()
    cleaned = re.sub(r"\b(data|information|details)\b$", "", cleaned).strip()
    for vp in _VERB_PREFIXES:
        pattern = rf"^{vp}\b[\s:,-]*"
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    words = cleaned.split()
    refined = " ".join(
        w.capitalize() if w not in {"of", "and", "for", "the", "to"} else w for w in words
    )
    return refined or raw


COMPANY_NAME = os.getenv("COMPANY_NAME", "Company")
EMAIL_SIGNATURE = os.getenv("EMAIL_SIGNATURE", "Best regards\n" + COMPANY_NAME)


def _allowed_domains() -> list[str]:
    raw = os.getenv("EMAIL_ALLOWED_DOMAINS", "")
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _allowed_recipients() -> list[str]:
    raw = os.getenv("EMAIL_ALLOWED_RECIPIENTS", "")
    return [r.strip().lower() for r in raw.split(",") if r.strip()]


def recipient_allowed(address: str) -> bool:
    """Return True if `address` passes the configured allowlist.

    If neither EMAIL_ALLOWED_DOMAINS nor EMAIL_ALLOWED_RECIPIENTS is set, every
    syntactically valid address is allowed (back-compat). When either is set,
    the address must match at least one of them.
    """
    if not address or not EMAIL_REGEX.match(address):
        return False
    address_lower = address.lower()

    domains = _allowed_domains()
    recipients = _allowed_recipients()
    if not domains and not recipients:
        return True

    if address_lower in recipients:
        return True

    domain = address_lower.split("@", 1)[1]
    if domain in domains:
        return True

    return False


def send_email(to: str, subject: str, body: str, html_body: str | None = None) -> str:
    """Send an email via SMTP (plain + optional HTML)."""
    if not recipient_allowed(to):
        return (
            f"Recipient '{to}' is not on the configured allowlist. "
            "Set EMAIL_ALLOWED_DOMAINS or EMAIL_ALLOWED_RECIPIENTS to permit it."
        )

    is_hf_spaces = os.getenv("SPACE_ID") is not None or os.getenv("SPACE_AUTHOR_NAME") is not None
    demo_mode = os.getenv("EMAIL_DEMO_MODE", "false").lower() == "true"

    if is_hf_spaces or demo_mode:
        return (
            "Email Approved & Simulated Successfully\n\n"
            f"To: {to}\nSubject: {subject}\n\n"
            f"Body:\n{body}\n\n"
            "Note: SMTP send was skipped (demo or HF Spaces mode)."
        )

    try:
        smtp_user = os.getenv("SMTP_USER") or os.getenv("FROM_EMAIL")
        smtp_password = os.getenv("SMTP_PASSWORD")
        if not smtp_user or not smtp_password:
            return "SMTP credentials not configured. Please set SMTP_USER and SMTP_PASSWORD."
        smtp_password = smtp_password.strip('"').strip("'")

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        msg = MIMEMultipart("alternative")
        msg["From"] = smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return f"Email sent successfully to {to}"
    except Exception as e:
        logger.warning("email_send_error", error=str(e))
        error_msg = str(e)
        if "Network is unreachable" in error_msg or "Connection refused" in error_msg:
            return (
                f"Network error: {error_msg}\n"
                "This usually means SMTP is blocked by the hosting provider. "
                "Set EMAIL_DEMO_MODE=true to simulate, or use an HTTP email API."
            )
        return f"Failed to send email: {error_msg}"


def draft_email(to: str, subject: str, body: str) -> str:
    """Produce reviewable draft block (plain text only)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return (
        "[DRAFT EMAIL]\n"
        f"Generated: {timestamp}\n"
        f"To: {to}\n"
        f"Subject: {subject}\n\n"
        f"{body}\n\n"
        "---\n"
        "This is a draft. Reply 'yes' to approve sending or 'no' to cancel."
    )


def _sanitize_context(raw: str) -> list[str]:
    lines: list[str] = []
    skip_patterns = [
        r"^\[.*?\]:?\s*$",
        r"^for context:",
        r"^i have drafted",
        r"approve.*email",
    ]

    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue

        s = re.sub(r"^\[.*?\]:\s*", "", s)
        s = re.sub(r"^[*\-•]+\s*", "", s)
        s = re.sub(r"\s+", " ", s).strip()

        if not s or s.lower().startswith("http"):
            continue

        if any(re.search(pattern, s.lower()) for pattern in skip_patterns):
            continue

        lines.append(s)
    return lines


def _parse_inventory(lines: list[str]) -> list[dict]:
    """Parse inventory from multi-line structured format."""
    items: list[dict] = []
    current_item: dict = {}

    for ln in lines:
        ln_clean = ln.strip()

        name_sku_match = re.search(
            r"\*?\*?\s*(.+?)\s*\(SKU:\s*([A-Z\-0-9]+)\)", ln_clean, re.IGNORECASE
        )
        if name_sku_match:
            if current_item and "name" in current_item:
                items.append(current_item)
            name = re.sub(r"\*+", "", name_sku_match.group(1)).strip()
            sku = name_sku_match.group(2).strip()
            current_item = {"name": name, "sku": sku, "qty": 0, "price": None, "ext": None}
            continue

        if current_item:
            stock_match = re.search(r"Stock:\s*(\d+)\s+units?", ln_clean, re.IGNORECASE)
            if stock_match:
                current_item["qty"] = int(stock_match.group(1))
                continue

            price_match = re.search(r"Price:\s*\$(\d+(?:\.\d+)?)", ln_clean, re.IGNORECASE)
            if price_match:
                current_item["price"] = float(price_match.group(1))
                if current_item.get("qty") and current_item["price"]:
                    current_item["ext"] = current_item["qty"] * current_item["price"]
                continue

    if current_item and "name" in current_item:
        items.append(current_item)

    return items


def _format_body(greeting: str, intro: str, sections: list[str], closing: str) -> str:
    parts: list[str] = [greeting, "", intro, ""]
    for sec in sections:
        parts.append(f"• {sec}")
    parts.extend(["", closing, "", EMAIL_SIGNATURE])
    return "\n".join(parts)


def _body_to_html(body: str) -> str:
    """Convert plain-text email body to styled HTML paragraphs and lists."""
    lines = body.splitlines()
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Bullet lines
        if stripped.startswith(("•", "-", "*")) and len(stripped) > 1:
            item = stripped.lstrip("•-* ").strip()
            # Markdown bold **text**
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(item))
            if not in_list:
                html_parts.append(
                    '<ul style="margin:12px 0;padding-left:20px;color:#374151;">'
                )
                in_list = True
            html_parts.append(f"<li style=\"margin-bottom:6px;\">{item}</li>")
            continue

        if in_list:
            html_parts.append("</ul>")
            in_list = False

        if not stripped:
            continue

        # Markdown ### heading
        if stripped.startswith("###"):
            text = html.escape(stripped.lstrip("#").strip())
            html_parts.append(
                f'<h3 style="margin:18px 0 6px;color:#111827;font-size:15px;">{text}</h3>'
            )
            continue

        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(stripped))
        html_parts.append(
            f'<p style="margin:8px 0;color:#374151;line-height:1.6;">{escaped}</p>'
        )

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _build_html(subject: str, body: str) -> str:
    """Render a full, responsive HTML email from subject + plain-text body."""
    company = html.escape(os.getenv("COMPANY_NAME", "Company"))
    safe_subject = html.escape(subject)
    year = datetime.now(timezone.utc).year
    body_html = _body_to_html(body)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{safe_subject}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);
                     padding:28px 32px;">
            <p style="margin:0;color:#ffffff;font-size:13px;
                      letter-spacing:1.5px;text-transform:uppercase;opacity:.75;">
              {company}
            </p>
            <h1 style="margin:6px 0 0;color:#ffffff;font-size:22px;
                       font-weight:700;line-height:1.3;">
              {safe_subject}
            </h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 32px 24px;">
            {body_html}
          </td>
        </tr>

        <!-- Divider -->
        <tr>
          <td style="padding:0 32px;">
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"/>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px 28px;">
            <p style="margin:0;font-size:13px;color:#6b7280;">
              &copy; {year} {company} &mdash; This email was generated by the
              Enterprise Agents Platform.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def compose_email_with_html(
    recipient: str, purpose: str, context_data: str
) -> Tuple[str, str]:
    """Compose a draft email; returns (plain_draft, html_variant).

    Used by routes for the auto-detect path. The LLM-facing tool wrapper
    `compose_email_from_context` returns only the plain draft string so
    Google ADK can serialize it as a tool result.
    """
    refined_purpose = _refine_purpose(purpose)
    cleaned = _sanitize_context(context_data)
    inventory_items = _parse_inventory(cleaned)

    if inventory_items:
        total_units = sum(i["qty"] for i in inventory_items)
        distinct = len(inventory_items)
        total_value = sum(i["ext"] for i in inventory_items if i["ext"] is not None)
        value_part = f" | Est. Value ${total_value:,.2f}" if total_value else ""
        subject = (
            f"{refined_purpose} Update – {total_units} Units ({distinct} Model(s)){value_part}"
            if refined_purpose
            else f"Inventory Update – {total_units} Units"
        )
    else:
        subject = f"{refined_purpose} Update" if refined_purpose else "Status Update"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    intro_parts: list[str] = []
    intro_parts.append(
        f"This message presents the current {refined_purpose.lower()} status."
        if refined_purpose
        else "This message presents current status update."
    )
    if inventory_items:
        total_units = sum(i["qty"] for i in inventory_items)
        distinct = len(inventory_items)
        total_value = sum(i["ext"] for i in inventory_items if i["ext"] is not None)
        if total_value:
            intro_parts.append(
                f"We maintain {total_units} total units across {distinct} model(s) "
                f"with an estimated gross value of ${total_value:,.2f}."
            )
        else:
            intro_parts.append(
                f"We maintain {total_units} total units across {distinct} model(s)."
            )
        min_qty = min(i["qty"] for i in inventory_items)
        if min_qty < 25:
            intro_parts.append(
                "One or more models are approaching low threshold; monitor replenishment schedule."
            )
        else:
            intro_parts.append(
                "All tracked models are within healthy stock ranges; no immediate replenishment required."
            )
    intro_parts.append(f"Snapshot generated {timestamp}.")
    intro = " ".join(intro_parts)

    narrative_lines: list[str] = []
    for it in inventory_items:
        unit_price = f"${it['price']:.2f}" if it["price"] is not None else "(price N/A)"
        value = f" (value ${it['ext']:.2f})" if it["ext"] is not None else ""
        narrative_lines.append(
            f"{it['name']} (SKU {it['sku']}) – {it['qty']} units at {unit_price}{value}."
        )

    inventory_line_patterns = [
        r"\(SKU:",
        r"Stock:\s*\d+",
        r"Price:\s*\$",
        r"Category:",
        r"Location:",
    ]
    supplemental = [
        ln
        for ln in cleaned
        if not any(re.search(pattern, ln, re.IGNORECASE) for pattern in inventory_line_patterns)
    ]

    sections = narrative_lines + supplemental

    body = _format_body(
        greeting="Dear Team,",
        intro=intro,
        sections=sections,
        closing="Please advise if any further breakdown, forward scheduling, or escalation is required.",
    )

    html_variant = _build_html(subject, body)
    plain_draft = draft_email(to=recipient, subject=subject, body=body)
    return plain_draft, html_variant


def compose_email_from_context(recipient: str, purpose: str, context_data: str) -> str:
    """LLM tool wrapper: returns only the plain-text draft."""
    plain, _ = compose_email_with_html(recipient, purpose, context_data)
    return plain
