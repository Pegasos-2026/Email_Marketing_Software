import React, { useState } from 'react';
import { ValidationReport, generateValidationReport } from '../services/emailValidator';
import '../styles/validation-report.css';

interface ValidationReportProps {
    report: ValidationReport;
    onAutoFixSuggestions?: (correctedEmails: Array<{ original: string; corrected: string; rowNumber: number }>) => void;
    onProceedWithImport?: () => void;
    onClose?: () => void;
}

const ValidationReportComponent: React.FC<ValidationReportProps> = ({
    report,
    onAutoFixSuggestions,
    onProceedWithImport,
    onClose,
}) => {
    const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

    const toggleRowExpanded = (rowNumber: number) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(rowNumber)) {
            newExpanded.delete(rowNumber);
        } else {
            newExpanded.add(rowNumber);
        }
        setExpandedRows(newExpanded);
    };

    const handleDownloadReport = () => {
        const csvContent = generateValidationReport(report);
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `validation_report_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const handleAutoFixSuggestions = () => {
        if (!onAutoFixSuggestions) return;

        const corrected = report.errors
            .filter(error => error.suggestion)
            .map(error => ({
                original: error.email,
                corrected: error.suggestion!,
                rowNumber: error.rowNumber,
            }));

        if (corrected.length > 0) {
            onAutoFixSuggestions(corrected);
        }
    };

    const successRate = report.totalRows > 0 ? ((report.validEmails / report.totalRows) * 100).toFixed(1) : '0';
    const hasSuggestions = report.errors.some(e => e.suggestion);

    return (
        <div className="validation-report-overlay">
            <div className="validation-report-panel">
                <div className="validation-report-header">
                    <h2>Email Validation Report</h2>
                    {onClose && (
                        <button className="close-btn" onClick={onClose}>
                            ×
                        </button>
                    )}
                </div>

                <div className="validation-summary-section">
                    <div className="summary-grid">
                        <div className="summary-item">
                            <div className="summary-label">Total Rows</div>
                            <div className="summary-value">{report.totalRows}</div>
                        </div>
                        <div className="summary-item success">
                            <div className="summary-label">Valid Emails</div>
                            <div className="summary-value">{report.validEmails}</div>
                        </div>
                        <div className="summary-item error">
                            <div className="summary-label">Invalid Emails</div>
                            <div className="summary-value">{report.invalidEmails}</div>
                        </div>
                        <div className="summary-item warning">
                            <div className="summary-label">Duplicates</div>
                            <div className="summary-value">{report.duplicateEmails}</div>
                        </div>
                        <div className="summary-item">
                            <div className="summary-label">Success Rate</div>
                            <div className="summary-value">{successRate}%</div>
                        </div>
                    </div>
                </div>

                {report.errors.length > 0 && (
                    <div className="validation-errors-section">
                        <h3>Validation Issues ({report.errors.length})</h3>
                        <div className="errors-table-wrap">
                            <table className="errors-table">
                                <thead>
                                    <tr>
                                        <th>Row</th>
                                        <th>Email</th>
                                        <th>Error</th>
                                        <th>Suggestion</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {report.errors.map((error) => (
                                        <tr key={`${error.rowNumber}-${error.email}`} className={`error-row error-type-${error.suggestion ? 'fixable' : 'unfixable'}`}>
                                            <td className="row-number">{error.rowNumber}</td>
                                            <td className="email-cell">
                                                <span className="email-text">{error.email || '(empty)'}</span>
                                            </td>
                                            <td className="error-cell">
                                                <span className="error-badge">{error.error}</span>
                                            </td>
                                            <td className="suggestion-cell">
                                                {error.suggestion ? (
                                                    <span className="suggestion-text">{error.suggestion}</span>
                                                ) : (
                                                    <span className="no-suggestion">—</span>
                                                )}
                                            </td>
                                            <td className="expand-cell">
                                                <button
                                                    className="expand-btn"
                                                    onClick={() => toggleRowExpanded(error.rowNumber)}
                                                    title={expandedRows.has(error.rowNumber) ? 'Collapse' : 'Expand'}
                                                >
                                                    {expandedRows.has(error.rowNumber) ? '▼' : '▶'}
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {report.validRecords.length > 0 && (
                    <div className="validation-valid-section">
                        <h3>Valid Emails ({report.validRecords.length})</h3>
                        <div className="valid-emails-preview">
                            {report.validRecords.slice(0, 5).map((record) => (
                                <div key={`${record.rowNumber}-${record.email}`} className="valid-email-item">
                                    <span className="row-badge">{record.rowNumber}</span>
                                    <span className="email-value">{record.email}</span>
                                </div>
                            ))}
                            {report.validRecords.length > 5 && (
                                <div className="more-valid-emails">
                                    ...and {report.validRecords.length - 5} more valid email(s)
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <div className="validation-actions">
                    <button className="btn-secondary" onClick={handleDownloadReport}>
                        Download Report
                    </button>
                    {hasSuggestions && onAutoFixSuggestions && (
                        <button className="btn-secondary" onClick={handleAutoFixSuggestions}>
                            Auto-Fix {report.errors.filter(e => e.suggestion).length} Issues
                        </button>
                    )}
                    {onProceedWithImport && report.validEmails > 0 && (
                        <button className="btn-primary" onClick={onProceedWithImport}>
                            Import {report.validEmails} Valid Contact{report.validEmails === 1 ? '' : 's'}
                        </button>
                    )}
                    {onClose && (
                        <button className="btn-secondary" onClick={onClose}>
                            Close
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ValidationReportComponent;
