/**
 * Domain-independent email validation for contact import.
 * Supports all legitimate providers and TLDs (.com, .co.in, .org.in, etc.).
 */

export interface EmailValidationResult {
    email: string;
    isValid: boolean;
    rowNumber: number;
    error?: string;
    suggestion?: string;
}

export interface ValidationReport {
    totalRows: number;
    validEmails: number;
    invalidEmails: number;
    duplicateEmails: number;
    errors: EmailValidationResult[];
    validRecords: Array<{ email: string; rowNumber: number }>;
}

const DOMAIN_TYPO_SUGGESTIONS: Record<string, string> = {
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
};

const LOCAL_PART_RE = /^[a-z0-9._%+-]+$/i;
const LABEL_RE = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?|xn--[a-z0-9-]{1,59})$/i;

function suggestDomain(domain: string): string | null {
    return DOMAIN_TYPO_SUGGESTIONS[domain.toLowerCase()] || null;
}

function validateDomainLabels(domain: string): { ok: boolean; error?: string } {
    if (!domain || domain.length > 253) {
        return { ok: false, error: 'Invalid domain length' };
    }
    if (domain.startsWith('.') || domain.endsWith('.') || domain.includes('..')) {
        return { ok: false, error: 'Invalid domain format' };
    }

    const labels = domain.split('.');
    if (labels.length < 2) {
        return { ok: false, error: 'Domain must include a TLD' };
    }

    for (const label of labels) {
        if (!label || label.length > 63 || !LABEL_RE.test(label)) {
            return { ok: false, error: 'Invalid domain label' };
        }
    }

    const tld = labels[labels.length - 1];
    if (!/^[a-z]{2,63}$/i.test(tld)) {
        return { ok: false, error: 'Invalid top-level domain' };
    }

    return { ok: true };
}

export function validateEmail(email: string, rowNumber: number): EmailValidationResult {
    const trimmedEmail = (email ?? '').trim();
    const normalized = trimmedEmail.toLowerCase();

    if (!normalized) {
        return { email, isValid: false, rowNumber, error: 'Email address is empty' };
    }

    if (/\s/.test(trimmedEmail)) {
        return {
            email,
            isValid: false,
            rowNumber,
            error: 'Email contains spaces or invalid whitespace',
            suggestion: normalized.replace(/\s+/g, ''),
        };
    }

    const atCount = normalized.split('@').length - 1;
    if (atCount === 0) {
        return { email, isValid: false, rowNumber, error: 'Missing @ symbol in email address' };
    }
    if (atCount > 1) {
        return { email, isValid: false, rowNumber, error: 'Multiple @ symbols found in email address' };
    }

    const [localPart, domainPart] = normalized.split('@');

    if (!localPart || localPart.length > 64) {
        return { email, isValid: false, rowNumber, error: 'Invalid local part (before @)' };
    }

    if (localPart.startsWith('.') || localPart.endsWith('.') || localPart.includes('..')) {
        return {
            email,
            isValid: false,
            rowNumber,
            error: 'Local part cannot start/end with a dot or contain consecutive dots',
        };
    }

    if (!LOCAL_PART_RE.test(localPart)) {
        return { email, isValid: false, rowNumber, error: 'Local part contains invalid characters' };
    }

    const domainCheck = validateDomainLabels(domainPart);
    if (!domainCheck.ok) {
        return { email, isValid: false, rowNumber, error: domainCheck.error || 'Invalid domain format' };
    }

    const suggestion = suggestDomain(domainPart);
    if (suggestion) {
        return {
            email,
            isValid: false,
            rowNumber,
            error: `Possible domain typo (${domainPart})`,
            suggestion: `${localPart}@${suggestion}`,
        };
    }

    return { email: normalized, isValid: true, rowNumber };
}

export function validateEmails(
    emailList: Array<{ email: string; rowNumber: number }>,
    onProgress?: (processed: number, total: number) => void
): ValidationReport {
    const errors: EmailValidationResult[] = [];
    const validRecords: Array<{ email: string; rowNumber: number }> = [];
    const seenEmails = new Set<string>();
    let duplicateCount = 0;
    const total = emailList.length;

    for (let index = 0; index < emailList.length; index++) {
        const record = emailList[index];
        const result = validateEmail(record.email, record.rowNumber);

        if (!result.isValid) {
            errors.push(result);
        } else if (seenEmails.has(result.email)) {
            duplicateCount++;
            errors.push({
                email: result.email,
                isValid: false,
                rowNumber: result.rowNumber,
                error: 'Duplicate email address in file',
            });
        } else {
            seenEmails.add(result.email);
            validRecords.push({ email: result.email, rowNumber: result.rowNumber });
        }

        if (onProgress && (index % 25 === 0 || index === total - 1)) {
            onProgress(index + 1, total);
        }
    }

    return {
        totalRows: emailList.length,
        validEmails: validRecords.length,
        invalidEmails: errors.length - duplicateCount,
        duplicateEmails: duplicateCount,
        errors,
        validRecords,
    };
}

export function parseCSVContent(content: string): Array<{ email: string; rowNumber: number }> {
    const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const lines = normalized.split('\n').filter((line) => line.trim());
    if (lines.length === 0) return [];
    const parsedRows = lines.map(parseCSVLine);
    return extractEmailRecordsFromCsvRows(parsedRows);
}

export function parseTXTContent(content: string): Array<{ email: string; rowNumber: number }> {
    const records: Array<{ email: string; rowNumber: number }> = [];
    const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
    lines.forEach((line, index) => {
        const email = line.trim();
        if (email && !email.startsWith('#')) {
            records.push({ email, rowNumber: index + 1 });
        }
    });
    return records;
}

function extractEmailRecordsFromCsvRows(rows: string[][]): Array<{ email: string; rowNumber: number }> {
    const EMAIL_HEADERS = new Set(['email', 'email_address', 'e_mail', 'emailaddress', 'mail', 'e-mail']);
    const records: Array<{ email: string; rowNumber: number }> = [];
    if (rows.length === 0) return records;

    const firstRow = rows[0].map((cell) => cell.trim());
    let startIndex = 0;
    let emailColIndex = 0;

    const hasHeader = firstRow.some((cell) =>
        EMAIL_HEADERS.has(cell.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_'))
    );

    if (hasHeader) {
        emailColIndex = firstRow.findIndex((cell) =>
            EMAIL_HEADERS.has(cell.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_'))
        );
        if (emailColIndex < 0) emailColIndex = 0;
        startIndex = 1;
    } else if (firstRow.some((cell) => cell.includes('@'))) {
        emailColIndex = firstRow.findIndex((cell) => cell.includes('@'));
        if (emailColIndex < 0) emailColIndex = 0;
        startIndex = 0;
    } else {
        emailColIndex = 0;
        startIndex = 0;
    }

    for (let i = startIndex; i < rows.length; i++) {
        const row = rows[i];
        const email = row[emailColIndex]?.trim() || '';
        if (email) {
            records.push({ email, rowNumber: i + 1 });
        }
    }

    return records;
}

function parseCSVLine(line: string): string[] {
    const fields: string[] = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        const nextChar = line[i + 1];

        if (char === '"') {
            if (inQuotes && nextChar === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            fields.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }

    if (current.length > 0 || line.endsWith(',')) {
        fields.push(current.trim());
    }

    return fields;
}

export function generateValidationReport(report: ValidationReport): string {
    const lines: string[] = [];
    lines.push('Email Validation Report');
    lines.push(`Generated: ${new Date().toISOString()}`);
    lines.push('');
    lines.push('=== SUMMARY ===');
    lines.push(`Total Rows: ${report.totalRows}`);
    lines.push(`Valid Emails: ${report.validEmails}`);
    lines.push(`Invalid Emails: ${report.invalidEmails}`);
    lines.push(`Duplicate Emails: ${report.duplicateEmails}`);
    lines.push('');

    if (report.errors.length > 0) {
        lines.push('=== VALIDATION ERRORS ===');
        lines.push('Row,Email,Error,Suggestion');
        for (const error of report.errors) {
            const suggestion = error.suggestion ? `"${error.suggestion}"` : '';
            lines.push(`${error.rowNumber},"${error.email}","${error.error}",${suggestion}`);
        }
        lines.push('');
    }

    if (report.validRecords.length > 0) {
        lines.push('=== VALID EMAILS ===');
        lines.push('Row,Email');
        for (const record of report.validRecords) {
            lines.push(`${record.rowNumber},"${record.email}"`);
        }
    }

    return lines.join('\n');
}

/** Quick check used in forms — accepts any valid domain. */
export function isValidEmailFormat(email: string): boolean {
    return validateEmail(email, 0).isValid;
}
