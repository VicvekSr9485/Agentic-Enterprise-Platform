import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

_VERB_PREFIXES = [
    "summarize", "provide", "draft", "compose", "check", "get", "give", "share",
    "list", "show", "generate", "create", "prepare"
]

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
    refined = " ".join(w.capitalize() if w not in {"of", "and", "for", "the", "to"} else w for w in words)
    return refined or raw

COMPANY_NAME = os.getenv("COMPANY_NAME", "Company")
EMAIL_SIGNATURE = os.getenv("EMAIL_SIGNATURE", "Best regards\n" + COMPANY_NAME)


def send_email(to: str, subject: str, body: str, html_body: str | None = None) -> str:
    """Send an email via SMTP (plain + optional HTML)."""
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

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return f"Email sent successfully to {to}"
    except Exception as e:
        return f"Failed to send email: {e}"


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
        r"approve.*email"
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
    items = []
    current_item = {}
    
    for ln in lines:
        ln_clean = ln.strip()
        
        # Match item name with SKU: "**Industrial Water Pump Model A** (SKU: PUMP-001)"
        name_sku_match = re.search(r'\*?\*?\s*(.+?)\s*\(SKU:\s*([A-Z\-0-9]+)\)', ln_clean, re.IGNORECASE)
        if name_sku_match:
            # Save previous item if exists
            if current_item and 'name' in current_item:
                items.append(current_item)
            # Start new item
            name = re.sub(r'\*+', '', name_sku_match.group(1)).strip()
            sku = name_sku_match.group(2).strip()
            current_item = {'name': name, 'sku': sku, 'qty': 0, 'price': None, 'ext': None}
            continue
        
        # Match stock: "Stock: 50 units"
        if current_item:
            stock_match = re.search(r'Stock:\s*(\d+)\s+units?', ln_clean, re.IGNORECASE)
            if stock_match:
                current_item['qty'] = int(stock_match.group(1))
                continue
            
            # Match price: "Price: $299.99"
            price_match = re.search(r'Price:\s*\$(\d+(?:\.\d+)?)', ln_clean, re.IGNORECASE)
            if price_match:
                current_item['price'] = float(price_match.group(1))
                if current_item.get('qty') and current_item['price']:
                    current_item['ext'] = current_item['qty'] * current_item['price']
                continue
    
    # Save last item
    if current_item and 'name' in current_item:
        items.append(current_item)
    
    return items

def _format_inventory_table(items: list[dict]) -> tuple[str, str]:
    if not items:
        return "", ""
    # Plain text table
    headers = ["Model", "SKU", "Qty", "Unit", "Value"]
    rows = []
    for it in items:
        unit_price = f"${it['price']:.2f}" if it['price'] is not None else "-"
        value = f"${it['ext']:.2f}" if it['ext'] is not None else "-"
        rows.append([it['name'], it['sku'], str(it['qty']), unit_price, value])
    col_widths = [max(len(row[i]) for row in rows + [headers]) for i in range(len(headers))]
    def _fmt(row):
        return " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers)))
    plain_lines = [ _fmt(headers), "-+-".join('-'*w for w in col_widths) ] + [ _fmt(r) for r in rows ]
    plain_table = "\n".join(plain_lines)

    html_rows = "".join(
        f"<tr><td>{it['name']}</td><td>{it['sku']}</td><td style='text-align:right'>{it['qty']}</td><td style='text-align:right'>{f'${it['price']:.2f}' if it['price'] else '-'}</td><td style='text-align:right'>{f'${it['ext']:.2f}' if it['ext'] else '-'}</td></tr>"
        for it in items
    )
    html_table = (
        "<table style='border-collapse:collapse;font-family:Arial;'>"
        "<thead><tr style='background:#f2f2f2'>"
        "<th style='padding:4px 8px;border:1px solid #ddd'>Model</th>"
        "<th style='padding:4px 8px;border:1px solid #ddd'>SKU</th>"
        "<th style='padding:4px 8px;border:1px solid #ddd;text-align:right'>Qty</th>"
        "<th style='padding:4px 8px;border:1px solid #ddd;text-align:right'>Unit</th>"
        "<th style='padding:4px 8px;border:1px solid #ddd;text-align:right'>Value</th>"
        "</tr></thead><tbody>" + html_rows + "</tbody></table>"
    )
    return plain_table, html_table


def _format_body(greeting: str, intro: str, sections: list[str], closing: str) -> str:
    parts: list[str] = [greeting, "", intro, ""]
    for sec in sections:
        parts.append(f"• {sec}")
    parts.extend(["", closing, "", EMAIL_SIGNATURE])
    return "\n".join(parts)


def _build_html(subject: str, sections: list[str], intro: str) -> str:
    li = "".join(f"<li>{s}</li>" for s in sections)
    return f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height:1.5; color:#222;">
    <h2 style="margin:0 0 12px 0;">{subject}</h2>
    <p>{intro}</p>
    <ul style="padding-left:18px;">{li}</ul>
    <p style="margin-top:18px;">{EMAIL_SIGNATURE.replace('\n', '<br/>')}</p>
    <hr style="margin:24px 0;"/>
    <p style="font-size:12px;color:#666;">This is a draft pending approval.</p>
  </body>
</html>
""".strip()


def compose_email_from_context(recipient: str, purpose: str, context_data: str) -> str:
    """Compose professional narrative (no tables) email from raw context."""
    refined_purpose = _refine_purpose(purpose)
    cleaned = _sanitize_context(context_data)
    inventory_items = _parse_inventory(cleaned)

    # Subject with summary metrics if inventory present
    if inventory_items:
        total_units = sum(i['qty'] for i in inventory_items)
        distinct = len(inventory_items)
        total_value = sum(i['ext'] for i in inventory_items if i['ext'] is not None)
        value_part = f" | Est. Value ${total_value:,.2f}" if total_value else ""
        subject = f"{refined_purpose} Update – {total_units} Units ({distinct} Model(s)){value_part}" if refined_purpose else f"Inventory Update – {total_units} Units"  
    else:
        subject = f"{refined_purpose} Update" if refined_purpose else "Status Update"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Intro paragraph
    intro_parts = [
        f"This message presents the current {refined_purpose.lower()} status." if refined_purpose else "This message presents current status update.",
    ]
    if inventory_items:
        total_units = sum(i['qty'] for i in inventory_items)
        distinct = len(inventory_items)
        total_value = sum(i['ext'] for i in inventory_items if i['ext'] is not None)
        if total_value:
            intro_parts.append(
                f"We maintain {total_units} total units across {distinct} model(s) with an estimated gross value of ${total_value:,.2f}."
            )
        else:
            intro_parts.append(
                f"We maintain {total_units} total units across {distinct} model(s)."
            )
        # Stock health assessment (simple heuristic)
        min_qty = min(i['qty'] for i in inventory_items)
        if min_qty < 25:
            intro_parts.append("One or more models are approaching low threshold; monitor replenishment schedule.")
        else:
            intro_parts.append("All tracked models are within healthy stock ranges; no immediate replenishment required.")
    intro_parts.append(f"Snapshot generated {timestamp}.")
    intro = " " .join(intro_parts)

    # Narrative item lines
    narrative_lines: list[str] = []
    for it in inventory_items:
        unit_price = f"${it['price']:.2f}" if it['price'] is not None else "(price N/A)"
        value = f" (value ${it['ext']:.2f})" if it['ext'] is not None else ""
        narrative_lines.append(
            f"{it['name']} (SKU {it['sku']}) – {it['qty']} units at {unit_price}{value}."
        )

    # Supplemental (non-inventory) cleaned lines - exclude lines that contributed to inventory parsing
    inventory_line_patterns = [r'\(SKU:', r'Stock:\s*\d+', r'Price:\s*\$', r'Category:', r'Location:']
    supplemental = [
        ln for ln in cleaned 
        if not any(re.search(pattern, ln, re.IGNORECASE) for pattern in inventory_line_patterns)
    ]

    # Merge sections: inventory narrative first, then supplemental context
    sections = narrative_lines + supplemental

    body = _format_body(
        greeting="Dear Team,",
        intro=intro,
        sections=sections,
        closing="Please advise if any further breakdown, forward scheduling, or escalation is required.",
    )

    # HTML variant narrative (simple list)
    html_sections = sections
    html_variant = _build_html(subject, html_sections, intro)
    os.environ["LAST_EMAIL_HTML"] = html_variant

    return draft_email(to=recipient, subject=subject, body=body)
