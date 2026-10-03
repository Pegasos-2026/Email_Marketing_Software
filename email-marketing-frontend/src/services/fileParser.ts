/**
 * Parses CSV and Excel contact import files into email records.
 */
import * as XLSX from 'xlsx';
import { parseCSVContent, parseTXTContent } from './emailValidator';

export interface EmailRecord {
    email: string;
    rowNumber: number;
}

const EMAIL_HEADER_NAMES = new Set([
    'email',
    'email_address',
    'e_mail',
    'emailaddress',
    'mail',
    'e-mail',
]);

const SUPPORTED_EXTENSIONS = ['.csv', '.xlsx', '.xls', '.txt'];

export function isSupportedImportFile(fileName: string): boolean {
    const lower = fileName.toLowerCase();
    return SUPPORTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function normalizeHeader(header: string): string {
    return header.trim().toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
}

function rowHasEmailHeader(cells: string[]): boolean {
    return cells.some((cell) => EMAIL_HEADER_NAMES.has(normalizeHeader(cell)));
}

function findEmailColumnIndex(cells: string[]): number {
    for (let i = 0; i < cells.length; i++) {
        if (EMAIL_HEADER_NAMES.has(normalizeHeader(cells[i]))) {
            return i;
        }
    }
    return 0;
}

function cellToString(value: unknown): string {
    if (value === null || value === undefined) return '';
    return String(value).trim();
}

/**
 * Extract email records from a 2D array of sheet/CSV rows.
 */
export function extractEmailRecordsFromRows(rows: unknown[][]): EmailRecord[] {
    const records: EmailRecord[] = [];
    if (rows.length === 0) return records;

    const firstRow = rows[0].map(cellToString);
    let startIndex = 0;
    let emailColIndex = 0;

    if (rowHasEmailHeader(firstRow)) {
        emailColIndex = findEmailColumnIndex(firstRow);
        startIndex = 1;
    } else if (firstRow.some((cell) => cell.includes('@'))) {
        emailColIndex = firstRow.findIndex((cell) => cell.includes('@'));
        if (emailColIndex < 0) emailColIndex = 0;
        startIndex = 0;
    } else {
        emailColIndex = 0;
        startIndex = 1;
    }

    for (let i = startIndex; i < rows.length; i++) {
        const row = rows[i];
        if (!row || row.length === 0) continue;

        const email = cellToString(row[emailColIndex]);
        if (email) {
            records.push({ email, rowNumber: i + 1 });
        }
    }

    return records;
}

async function parseExcelFile(file: File): Promise<EmailRecord[]> {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array', cellDates: false });
    const sheetName = workbook.SheetNames[0];

    if (!sheetName) {
        throw new Error('Excel file contains no worksheets');
    }

    const sheet = workbook.Sheets[sheetName];
    const rawRows = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
        header: 1,
        defval: '',
        raw: false,
    });

    return extractEmailRecordsFromRows(rawRows);
}

/**
 * Parse a CSV or Excel file into email records.
 */
export async function parseImportFile(file: File): Promise<EmailRecord[]> {
    if (!isSupportedImportFile(file.name)) {
        throw new Error('Unsupported file type. Please upload CSV, Excel (.xlsx/.xls), or TXT (.txt).');
    }

    const lowerName = file.name.toLowerCase();

    if (lowerName.endsWith('.xlsx') || lowerName.endsWith('.xls')) {
        return parseExcelFile(file);
    }

    const content = await file.text();

    if (lowerName.endsWith('.txt')) {
        return parseTXTContent(content);
    }

    return parseCSVContent(content);
}

/**
 * Build a CSV string with a proper header for backend import.
 */
export function buildValidatedImportCsv(emails: string[]): string {
    const lines = ['email', ...emails.map((email) => `"${email.replace(/"/g, '""')}"`)];
    return lines.join('\n');
}
