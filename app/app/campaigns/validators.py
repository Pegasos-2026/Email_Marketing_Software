import re
from django.core.exceptions import ValidationError
import os


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email: {email}")
    return True


def validate_csv_headers(headers, required):
    """Validate CSV has required headers"""
    missing = [h for h in required if h not in headers]
    if missing:
        raise ValidationError(f"Missing columns: {', '.join(missing)}")
    return True


def validate_phone(phone):
    """Validate phone number"""
    if phone and not re.match(r'^\+?1?\d{9,15}$', phone):
        raise ValidationError(f"Invalid phone: {phone}")
    return True
# campaigns/utils/helpers.py

def clean_csv_data(data):
    """Clean CSV data"""
    if isinstance(data, str):
        return data.strip()
    return data


def format_phone_number(phone):
    """Format phone number"""
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone


def generate_import_summary(created, updated, skipped):
    """Generate import summary message"""
    total = created + updated + skipped
    return {
        'total': total,
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'message': f"Processed {total} rows: {created} created, {updated} updated, {skipped} skipped"
    }
# campaigns/utils/exceptions.py

class ContactImportError(Exception):
    """Base exception for contact import errors"""
    pass


class InvalidCSVError(ContactImportError):
    """Invalid CSV file"""
    pass


class InvalidEmailError(ContactImportError):
    """Invalid email address"""
    pass

MAX_FILE_SIZE=5*1024*1024 #5MB
ALLOWED_EXTENSIONS=[
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx"
]
def validate_attachment(file):
    if file.size > MAX_FILE_SIZE:
        raise ValidationError("File size must be under 5MB")
    ext=os.path.splitext(file.name)[1][1:].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Unsupported file Type.Allowed:pdf,png,jpg,jpeg,doc,docx,xls,xlsx,ppt,pptx")