"""Domain-independent email validation for contact import."""
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email

# Known typo domains → suggested correction (optional auto-fix)
DOMAIN_TYPO_SUGGESTIONS = {
    'gmai.com': 'gmail.com',
    'gmial.com': 'gmail.com',
    'gmal.com': 'gmail.com',
    'gmail.co': 'gmail.com',
    'gmail.cm': 'gmail.com',
    'gmil.com': 'gmail.com',
    'yahou.com': 'yahoo.com',
    'yaho.com': 'yahoo.com',
    'yahoo.co': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'hotmail.co': 'hotmail.com',
    'outlook.co': 'outlook.com',
    'outlok.com': 'outlook.com',
    'iclod.com': 'icloud.com',
    'icloud.co': 'icloud.com',
    'protonmail.co': 'protonmail.com',
    'protonmai.com': 'protonmail.com',
    'rediffmail.co': 'rediffmail.com',
    'redifmail.com': 'rediffmail.com',
}

LABEL_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?|xn--[a-z0-9-]{1,59})$', re.IGNORECASE)
LOCAL_PART_RE = re.compile(r'^[a-z0-9._%+\-]+$', re.IGNORECASE)


def normalize_email(email):
    if email is None:
        return ''
    return str(email).strip().lower()


def suggest_domain_correction(domain):
    return DOMAIN_TYPO_SUGGESTIONS.get(domain.lower())


def validate_domain_labels(domain):
    """Validate domain structure including multi-part TLDs (.co.in, .org.in, etc.)."""
    if not domain or len(domain) > 253:
        return False, 'Invalid domain length'

    if domain.startswith('.') or domain.endswith('.') or '..' in domain:
        return False, 'Invalid domain format'

    labels = domain.split('.')
    if len(labels) < 2:
        return False, 'Domain must include a TLD'

    for label in labels:
        if not label or len(label) > 63:
            return False, 'Invalid domain label'
        if not LABEL_RE.match(label):
            return False, 'Invalid domain label characters'

    tld = labels[-1]
    if not re.match(r'^[a-z]{2,63}$', tld, re.IGNORECASE):
        return False, 'Invalid top-level domain'

    return True, None


def validate_contact_email(email, row_number=None):
    """
    Validate a single email address.
    Returns dict: {email, is_valid, error, suggestion, row}
    """
    original = email if email is not None else ''
    normalized = normalize_email(original)
    row = row_number or 0

    if not normalized:
        return {
            'email': original,
            'normalized_email': '',
            'is_valid': False,
            'error': 'Email address is empty',
            'suggestion': None,
            'row': row,
        }

    if normalized != original.strip().lower() or re.search(r'\s', original):
        pass  # normalized below

    if normalized.count('@') != 1:
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': 'Email must contain exactly one @ symbol',
            'suggestion': None,
            'row': row,
        }

    local, domain = normalized.rsplit('@', 1)

    if not local or len(local) > 64:
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': 'Invalid local part (before @)',
            'suggestion': None,
            'row': row,
        }

    if local.startswith('.') or local.endswith('.') or '..' in local:
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': 'Local part cannot start/end with a dot or contain consecutive dots',
            'suggestion': None,
            'row': row,
        }

    if not LOCAL_PART_RE.match(local):
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': 'Local part contains invalid characters',
            'suggestion': None,
            'row': row,
        }

    domain_ok, domain_error = validate_domain_labels(domain)
    if not domain_ok:
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': domain_error or 'Invalid domain format',
            'suggestion': None,
            'row': row,
        }

    suggestion = suggest_domain_correction(domain)
    if suggestion:
        suggested_email = f'{local}@{suggestion}'
        return {
            'email': original,
            'normalized_email': normalized,
            'is_valid': False,
            'error': f'Possible domain typo ({domain})',
            'suggestion': suggested_email,
            'row': row,
        }

    try:
        django_validate_email(normalized)
    except ValidationError:
        # Keep accepting business/organizational domains when our structural checks pass.
        # Django's validator is stricter and can reject some otherwise valid addresses.
        pass

    return {
        'email': original,
        'normalized_email': normalized,
        'is_valid': True,
        'error': None,
        'suggestion': None,
        'row': row,
    }


def validate_email_batch(rows, email_key='email'):
    """
    Validate a list of row dicts. Detect duplicates within the batch.
    Returns validation summary suitable for preview API.
    """
    errors = []
    valid_records = []
    seen = set()
    duplicate_count = 0

    for idx, row in enumerate(rows, start=2):
        raw_email = row.get(email_key, '') if isinstance(row, dict) else ''
        row_number = row.get('_row', idx) if isinstance(row, dict) else idx
        result = validate_contact_email(raw_email, row_number=row_number)

        if not result['is_valid']:
            errors.append({
                'row': result['row'],
                'email': result['email'] or '(empty)',
                'error': result['error'],
                'suggestion': result['suggestion'],
            })
            continue

        email = result['normalized_email']
        if email in seen:
            duplicate_count += 1
            errors.append({
                'row': result['row'],
                'email': email,
                'error': 'Duplicate email in import file',
                'suggestion': None,
            })
            continue

        seen.add(email)
        valid_records.append({
            'row': result['row'],
            'email': email,
            'name': (row.get('name') or '').strip() if isinstance(row, dict) else '',
            'is_subscribed': row.get('is_subscribed', True) if isinstance(row, dict) else True,
        })

    total = len(rows)
    invalid_count = len(errors) - duplicate_count

    return {
        'total_rows': total,
        'valid_count': len(valid_records),
        'invalid_count': max(invalid_count, 0),
        'duplicate_count': duplicate_count,
        'errors': errors,
        'valid_records': valid_records,
        'valid_preview': valid_records[:25],
        'error_preview': errors[:25],
    }
