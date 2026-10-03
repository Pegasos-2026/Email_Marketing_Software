from urllib.parse import quote, urlparse


def is_transient_network_error(message):
    """True for DNS/connectivity blips that may succeed on retry."""
    text = (message or '').lower()
    markers = (
        'getaddrinfo failed',
        'urlopen error',
        '10051',
        '11001',
        'network is unreachable',
        'connection refused',
        'connection reset',
        'timed out',
        'timeout',
        'temporary failure',
        'nodename nor servname',
        'failed to establish a new connection',
        'name or service not known',
    )
    return any(marker in text for marker in markers)


def is_public_site_url(site_url):
    """Return True when SITE_URL is a public http(s) host (not localhost or private IP)."""
    if not site_url:
        return False

    parsed = urlparse(site_url.strip())
    if parsed.scheme not in ('http', 'https'):
        return False

    host = (parsed.hostname or '').lower()
    if not host:
        return False

    if host in ('localhost', '127.0.0.1', '0.0.0.0', '[::1]'):
        return False

    if host.startswith('192.168.') or host.startswith('10.'):
        return False

    if host.startswith('172.'):
        parts = host.split('.')
        if len(parts) >= 2 and parts[1].isdigit():
            second_octet = int(parts[1])
            if 16 <= second_octet <= 31:
                return False

    return True


def format_list_unsubscribe(unsubscribe_url=None, mailto_email=None):
    """Build a List-Unsubscribe header value using https and/or mailto links."""
    parts = []
    if unsubscribe_url:
        parts.append(f"<{unsubscribe_url}>")
    if mailto_email:
        address = mailto_email.strip()
        if address:
            parts.append(f"<mailto:{address}?subject={quote('Unsubscribe')}>")
    return ", ".join(parts) if parts else None


def normalize_email_html(html_content):
    """Wrap bare HTML fragments in a minimal document so clients see a complete message."""
    content = (html_content or "").strip()
    if not content:
        return content
    lower = content.lower()
    if "<html" in lower and "<body" in lower:
        return content
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset=\"utf-8\"></head>"
        f"<body style=\"font-family:Arial,sans-serif;line-height:1.5;color:#111827;\">{content}</body>"
        "</html>"
    )


def personalize_campaign_text(text, contact_name, contact_email, recipient_id=None):
    """Replace merge tags so each outbound message is unique to the recipient."""
    if not text:
        return text
    name = (contact_name or "").strip() or "there"
    email = (contact_email or "").strip()
    personalized = text.replace("{{name}}", name)
    personalized = personalized.replace("{{email}}", email)
    if recipient_id is not None and "{{id}}" in personalized:
        personalized = personalized.replace("{{id}}", str(recipient_id))
    return personalized


def add_recipient_unique_plain_marker(plain_text, recipient_id=None):
    """Append a unique invisible marker so mailbox providers do not treat copies as bulk duplicates."""
    plain = (plain_text or '').rstrip()
    if not plain or recipient_id is None:
        return plain_text
    unique_marker = '\u200b' * ((int(recipient_id) % 7) + 1)
    return plain + unique_marker


def unique_subject_for_recipient(subject, recipient_id=None):
    """Make each subject line unique invisibly so Gmail does not batch identical subjects."""
    text = (subject or '').strip()
    if not text or recipient_id is None:
        return subject
    invisible = '\u200c' * ((int(recipient_id) % 5) + 1)
    return text + invisible


def differentiate_plain_for_recipient(plain_text, recipient_id=None, contact_email=None):
    """
    Scatter invisible unique characters through the body so each copy is not byte-identical.
    Gmail often hides duplicate bulk mail in All Mail when many copies share the same content.
    """
    plain = (plain_text or '').rstrip()
    if not plain or recipient_id is None:
        return plain_text

    markers = ('\u200b', '\u200c', '\u200d', '\ufeff')
    rid = int(recipient_id)
    blocks = plain.split('\n\n')
    updated = []
    for index, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
        if len(block) > 12:
            pos = (rid + index * 11) % max(1, len(block) - 1)
            marker = markers[(rid + index) % len(markers)]
            block = block[:pos] + marker + block[pos:]
        updated.append(block)
    return '\n\n'.join(updated)


def prepare_personal_inbox_delivery(
    subject,
    plain_text,
    recipient_id=None,
    contact_email=None,
    differentiate=True,
):
    """Apply per-recipient differentiation for inbox-priority bulk sends only."""
    if differentiate and recipient_id is not None:
        subject = unique_subject_for_recipient(subject, recipient_id)
        plain = differentiate_plain_for_recipient(plain_text, recipient_id, contact_email)
        plain = add_recipient_unique_plain_marker(plain, recipient_id)
    else:
        plain = plain_text
    return subject, plain


def resolve_campaign_reply_to(from_email, reply_to=None):
    """
    Replies should go to the campaign From address on the sending domain.
    Ignore personal Gmail/login addresses accidentally set as Reply-To.
    """
    from_addr = (from_email or '').strip()
    reply = (reply_to or '').strip()
    if not from_addr:
        return reply or None
    if not reply:
        return from_addr
    from_domain = from_addr.split('@')[-1].lower()
    reply_domain = reply.split('@')[-1].lower()
    if reply_domain != from_domain:
        return from_addr
    return reply


def add_recipient_unique_marker(html_content, recipient_id, contact_email):
    """Add a unique hidden marker so mailbox providers do not treat copies as duplicate bulk mail."""
    marker = f"<!-- pegasos-recipient:{recipient_id}:{quote(contact_email or '', safe='')} -->"
    lower = html_content.lower()
    if "</body>" in lower:
        idx = lower.rfind("</body>")
        return html_content[:idx] + marker + html_content[idx:]
    return html_content + marker


def normalize_plain_text_urls(text):
    """Unwrap label (https://url) patterns and ensure URLs are clickable in plain email."""
    import re

    if not text:
        return text
    updated = re.sub(r'([^\s(]+)\s*\((https?://[^)]+)\)', r'\2', text)
    paragraphs = []
    for block in re.split(r'\n\n+', updated):
        lines = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            lines.append(line)
            if re.match(r'^www\.[^\s]+$', line, re.IGNORECASE):
                https_url = f'https://{line}'
                if not any(
                    https_url.lower() in existing.lower()
                    for existing in lines
                    if existing.lower().startswith('http')
                ):
                    lines.append(https_url)
        if lines:
            paragraphs.append('\n'.join(lines))
    return '\n\n'.join(paragraphs)


def _linkify_plain_for_html(text):
    """Turn URLs in plain text into clickable links for the HTML part of inbox emails."""
    import re

    if not text:
        return text

    def replace_url(match):
        url = match.group(0)
        href = url if url.lower().startswith('http') else f'https://{url}'
        return (
            f'<a href="{href}" style="color:#1a73e8;text-decoration:underline;" '
            f'target="_blank" rel="noopener noreferrer">{url}</a>'
        )

    linked = re.sub(r'https?://[^\s<>&"]+', replace_url, text)
    return re.sub(r'(?<!://)(?<![\w.@])www\.[^\s<>&"]+', replace_url, linked)


def apply_inbox_friendly_format(html_content, plain_text_content=None, from_name=None):
    """
    Shape content like a personal 1:1 email.
    Gmail often routes HTML-heavy marketing mail to Promotions/Updates instead of Primary.
    """
    import re

    plain = (plain_text_content or "").strip()
    if not plain and html_content:
        plain = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html_content)
        plain = re.sub(r"(?i)<br\s*/?>", "\n", plain)
        plain = re.sub(r"(?i)</p\s*>", "\n\n", plain)
        plain = re.sub(r"(?s)<.*?>", "", plain)
        plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
    plain = normalize_plain_text_urls(plain)

    if plain:
        blocks = [block.strip() for block in plain.split("\n\n") if block.strip()]
        if not blocks:
            blocks = [line.strip() for line in plain.split("\n") if line.strip()]
        body_html = "".join(
            f'<p style="{_inbox_block_style(compact="\n" in block and block.count("\n") <= 5)}">'
            f'{_linkify_plain_for_html(block.replace(chr(10), "<br>"))}</p>'
            for block in blocks
        )
    else:
        body_html = (html_content or "").strip()

    signature_name = (from_name or "").strip()
    signature = ""
    if signature_name and signature_name.lower() not in plain.lower():
        signature = (
            f'<p style="margin:18px 0 0;{_inbox_block_style(compact=True).replace("margin:0 0 14px;", "")}">'
            f"Regards,<br>{signature_name}</p>"
        )

    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head>"
        "<body style=\"margin:0;padding:0;background:#fff;\">"
        f"{body_html}{signature}</body></html>"
    )
    return html, plain


def clean_plain_text_layout(text):
    """Preserve paragraph breaks (blank lines) and single line breaks within a paragraph."""
    import re

    if not text:
        return ''
    paragraphs = []
    for block in re.split(r'\n\n+', text):
        lines = [re.sub(r'\s+', ' ', line).strip() for line in block.splitlines()]
        lines = [line for line in lines if line]
        if lines:
            paragraphs.append('\n'.join(lines))
    return '\n\n'.join(paragraphs)


def _inbox_block_style(compact=False):
    base = 'font-family:Georgia,serif;font-size:15px;color:#222;text-align:left;'
    if compact:
        return f'margin:0 0 14px;{base}line-height:1.2;'
    return f'margin:0 0 14px;{base}line-height:1.6;'


_INBOX_ALLOWED_TAGS = frozenset(
    ('p', 'div', 'br', 'a', 'span', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li')
)
_INBOX_ALLOWED_ATTRS = frozenset(('style', 'href', 'target', 'rel', 'align'))


def is_prepared_campaign_html(html_content):
    """True when HTML is already a full document from the campaign/inbox pipeline."""
    html = (html_content or '').strip().lower()
    return '<html' in html and '<body' in html


def _merge_align_into_style(tag_html, attrs):
    """Convert legacy align=\"justify\" into inline style for consistent rendering."""
    import re

    align_match = re.search(r'align=["\']([^"\']+)["\']', tag_html, re.IGNORECASE)
    if not align_match:
        return attrs
    align_value = align_match.group(1).strip().lower()
    if align_value not in ('left', 'right', 'center', 'justify'):
        return attrs
    style = attrs.get('style', '')
    if 'text-align' in style.lower():
        return attrs
    style = f'{style};' if style and not style.rstrip().endswith(';') else style
    attrs['style'] = f'{style}text-align:{align_value};'.lstrip(';')
    return attrs


def sanitize_simple_inbox_html(html_content):
    """Keep safe tags and inline styles for inbox-priority HTML alternative."""
    import re

    content = (html_content or '').strip()
    if not content:
        return ''

    content = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', content)
    content = re.sub(r'(?is)<!DOCTYPE[^>]*>', '', content)
    for wrapper in ('html', 'head', 'body'):
        content = re.sub(rf'(?is)</?{wrapper}[^>]*>', '', content)

    content = re.sub(r'(?is)</tr\s*>', '\n', content)
    content = re.sub(r'(?is)</td\s*>', ' ', content)
    content = re.sub(r'(?is)<(table|tbody|thead|tfoot|tr|td|th)[^>]*>', '', content)

    def clean_tag(match):
        tag_html = match.group(0)
        lowered = tag_html.lower()
        if lowered.startswith('<br'):
            return '<br>'

        tag_match = re.match(r'(?is)</?(?P<name>[a-z][a-z0-9]*)', tag_html)
        if not tag_match:
            return ''
        name = tag_match.group('name').lower()
        if name not in _INBOX_ALLOWED_TAGS:
            return ''

        if tag_html.startswith('</'):
            return f'</{name}>'

        attrs = {}
        for attr_name in _INBOX_ALLOWED_ATTRS:
            attr_match = re.search(
                rf'{attr_name}=["\']([^"\']*)["\']',
                tag_html,
                re.IGNORECASE,
            )
            if attr_match:
                attrs[attr_name.lower()] = attr_match.group(1).strip()

        attrs = _merge_align_into_style(tag_html, attrs)
        attrs.pop('align', None)

        if name == 'a':
            href = attrs.get('href', '')
            if not href or href == '#':
                return ''
            attrs.setdefault('target', '_blank')
            attrs.setdefault('rel', 'noopener noreferrer')

        attr_parts = [f'{key}="{value}"' for key, value in attrs.items()]
        attr_string = f' {" ".join(attr_parts)}' if attr_parts else ''
        return f'<{name}{attr_string}>'

    return re.sub(r'(?is)<[^>]+>', clean_tag, content).strip()


def wrap_inbox_priority_html(body_html, from_name=None):
    """Wrap sanitized inbox HTML in a minimal document."""
    body = (body_html or '').strip()
    if not body:
        return ''

    signature_name = (from_name or '').strip()
    signature = ''
    if signature_name and signature_name.lower() not in body.lower():
        signature = (
            f'<p style="{_inbox_block_style(compact=True)}">'
            f'Regards,<br>{signature_name}</p>'
        )

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0;padding:0;background:#fff;text-align:left;">'
        f'{body}{signature}</body></html>'
    )


def is_rich_marketing_html(html_content):
    import re

    html = (html_content or '').strip()
    if not html:
        return False
    lower = html.lower()
    if re.search(r'<(table|td|tr|tbody|thead)[\s>]', lower):
        return True
    if re.search(r'<style[\s>]', html, re.IGNORECASE):
        return True
    if '<html' in lower and len(html) > 300:
        return True
    if re.search(r'<div[\s>]', html, re.IGNORECASE) and len(html) > 800:
        return True
    return len(html) > 1500


def html_to_plain_text(html_content):
    import re

    if not html_content:
        return ''
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', html_content)
    text = re.sub(
        r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda match: (
            match.group(1).strip()
            if (match.group(1) or '').strip() not in ('', '#')
            else re.sub(r'\s+', ' ', match.group(2)).strip()
        ),
        text,
    )
    text = re.sub(r'(?i)</td>', ' ', text)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p\s*>', '\n\n', text)
    text = re.sub(r'(?i)</tr\s*>', '\n', text)
    text = re.sub(r'(?i)</li\s*>', '\n', text)
    text = re.sub(r'(?s)<.*?>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&rarr;', '->', text)
    return clean_plain_text_layout(normalize_plain_text_urls(text))


def resolve_inbox_priority_plain(html_content=None, plain_text_content=None):
    """
    Choose the plain body for inbox-priority sends.
    Prefer HTML conversion when it contains more complete content (e.g. signature with phone).
    """
    plain_from_html = html_to_plain_text(html_content) if (html_content or '').strip() else ''
    plain_from_field = (plain_text_content or '').strip()

    if plain_from_field and plain_from_html:
        if (
            len(plain_from_html) > len(plain_from_field) + 20
            or plain_from_field in plain_from_html
            or not _plain_has_contact_details(plain_from_field)
            and _plain_has_contact_details(plain_from_html)
        ):
            return plain_from_html
        return plain_from_field
    if plain_from_html:
        return plain_from_html
    return plain_from_field


def _plain_has_contact_details(text):
    import re

    if not text:
        return False
    lowered = text.lower()
    if 'http' in lowered or 'www.' in lowered:
        return True
    return bool(re.search(r'\+?\d[\d\s\-()]{7,}', text))


def replace_generic_greeting(text, contact_name):
    import re

    if not text:
        return text
    name = (contact_name or '').strip() or 'there'
    patterns = [
        r'Dear\s+Sir/Madam',
        r'Dear\s+Sir\s+or\s+Madam',
        r'Dear\s+Customer',
        r'Dear\s+Valued\s+Customer',
        r'Dear\s+Sir',
        r'Dear\s+Madam',
    ]
    updated = text
    for pattern in patterns:
        updated = re.sub(pattern, f'Hi {name}', updated, flags=re.IGNORECASE)
    return updated


def personalize_subject_for_inbox(subject, contact_name, contact_email=None):
    """Only personalize the subject when the template includes merge tags."""
    name = (contact_name or '').strip() or 'there'
    email = (contact_email or '').strip()
    subject = (subject or '').strip()
    if not subject:
        return subject
    if '{{name}}' in subject:
        subject = subject.replace('{{name}}', name)
    if '{{email}}' in subject:
        subject = subject.replace('{{email}}', email)
    return subject


def content_uses_personalization(html_content=None, plain_text_content=None, subject=None):
    combined = f"{html_content or ''}{plain_text_content or ''}{subject or ''}"
    return '{{name}}' in combined or '{{email}}' in combined


def normalize_subject_for_inbox(subject):
    """Tone down promotional subject lines so Gmail is more likely to show Primary inbox."""
    import re

    cleaned = (subject or '').strip()
    if not cleaned:
        return cleaned
    cleaned = re.sub(r'!{2,}', '!', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if cleaned.isupper() and len(cleaned) > 8:
        cleaned = cleaned.title()
    return cleaned


def prepare_inbox_priority_message(
    html_content,
    plain_text_content,
    contact_name,
    contact_email,
    from_name,
    subject,
    recipient_id=None,
    differentiate_recipients=True,
    include_html_alternative=True,
):
    """Prepare a plain personal-style email for Gmail Primary inbox placement."""
    uses_personalization = content_uses_personalization(
        html_content,
        plain_text_content,
        subject,
    )
    personalized_subject = personalize_campaign_text(subject, contact_name, contact_email, recipient_id)
    personalized_subject = personalize_subject_for_inbox(personalized_subject, contact_name, contact_email)
    personalized_subject = normalize_subject_for_inbox(personalized_subject)

    plain = resolve_inbox_priority_plain(html_content, plain_text_content)
    plain = normalize_plain_text_urls(plain)
    plain = personalize_campaign_text(plain, contact_name, contact_email, recipient_id)
    if uses_personalization and '{{name}}' in f"{plain_text_content or ''}{html_content or ''}":
        plain = replace_generic_greeting(plain, (contact_name or '').strip() or 'there')

    source_html = (html_content or '').strip()
    if source_html:
        personalized_html = personalize_campaign_text(
            source_html,
            contact_name,
            contact_email,
            recipient_id,
        )
        if uses_personalization and '{{name}}' in source_html:
            personalized_html = replace_generic_greeting(
                personalized_html,
                (contact_name or '').strip() or 'there',
            )
        sanitized = sanitize_simple_inbox_html(personalized_html)
        if sanitized:
            html = wrap_inbox_priority_html(sanitized, from_name=from_name)
        else:
            html, plain = apply_inbox_friendly_format('', plain, from_name=from_name)
    else:
        html, plain = apply_inbox_friendly_format('', plain, from_name=from_name)
    personalized_subject, plain = prepare_personal_inbox_delivery(
        personalized_subject,
        plain,
        recipient_id=recipient_id,
        contact_email=contact_email,
        differentiate=differentiate_recipients,
    )
    if recipient_id is not None and include_html_alternative:
        html = add_recipient_unique_marker(html, recipient_id, contact_email)
    return personalized_subject, plain, html


def should_use_inbox_friendly_format(html_content, plain_text_content=None):
    """
    Use plain personal formatting only for simple campaigns.
    Rich HTML templates (tables, layouts) should be sent as designed.
    """
    html = (html_content or "").strip()
    if not html:
        return True

    lower = html.lower()
    if "<table" in lower or len(html) > 1500:
        return False
    if "letter-spacing" in lower or "text-transform:uppercase" in lower.replace(" ", ""):
        return False
    return len(html) < 700
