import { contactService } from '../services/contactService';
import { ValidationReport, validateEmails } from '../services/emailValidator';
import { buildValidatedImportCsv, isSupportedImportFile, parseImportFile } from '../services/fileParser';

export interface ContactImportSummary {
    created: number;
    updated: number;
    skipped: number;
    total: number;
    contact_ids?: number[];
    errors: Array<{ row: number; email: string; error: string }>;
    duplicate_count?: number;
    invalid_count?: number;
    sheet_rows?: number;
    data_rows_in_sheet?: number;
    blank_rows_in_sheet?: number;
}

export interface ContactImportResponse {
    success?: boolean;
    summary: ContactImportSummary;
    import_log_id?: number;
}

export async function validateContactImportFile(
    file: File,
    onProgress?: (message: string, percent?: number) => void,
): Promise<ValidationReport> {
    if (!isSupportedImportFile(file.name)) {
        throw new Error('Please upload a CSV, Excel (.xlsx, .xls), or TXT (.txt) file');
    }

    onProgress?.('Reading file...');
    const emailRecords = await parseImportFile(file);

    if (emailRecords.length === 0) {
        throw new Error('No email addresses found in the file. Ensure the file has an "email" column.');
    }

    onProgress?.(`Validating ${emailRecords.length} email address(es)...`, 0);
    return validateEmails(emailRecords, (processed, total) => {
        const percent = Math.round((processed / total) * 100);
        onProgress?.(`Validating email addresses... ${percent}%`, percent);
    });
}

export async function importValidatedContactFile(
    validationReport: ValidationReport,
    listId?: number,
): Promise<ContactImportResponse> {
    if (validationReport.validEmails === 0) {
        throw new Error('No valid emails to import');
    }

    const csvContent = buildValidatedImportCsv(
        validationReport.validRecords.map((record) => record.email),
    );
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const file = new File([blob], 'validated_contacts.csv', { type: 'text/csv' });
    return contactService.importContacts(file, listId) as Promise<ContactImportResponse>;
}

export function applyAutoFixSuggestions(
    report: ValidationReport,
    correctedEmails: Array<{ original: string; corrected: string; rowNumber: number }>,
): ValidationReport {
    const updatedErrors = report.errors.filter(
        (error) => !correctedEmails.some((item) => item.original === error.email),
    );
    const validRecords = [
        ...report.validRecords,
        ...correctedEmails.map((item) => ({ email: item.corrected, rowNumber: item.rowNumber })),
    ].sort((a, b) => a.rowNumber - b.rowNumber);

    return {
        totalRows: report.totalRows,
        validEmails: validRecords.length,
        invalidEmails: updatedErrors.filter((error) => error.error !== 'Duplicate email address in file').length,
        duplicateEmails: report.duplicateEmails,
        errors: updatedErrors,
        validRecords,
    };
}
