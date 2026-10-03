import React, { useState } from 'react';
import { contactService } from '../services/contactService';
import '../styles/bulk-email.css';

interface BulkEmailComposeProps {
    isOpen: boolean;
    onClose: () => void;
    contactIds: number[];
    listId?: number;
    importedCount: number;
}

const BulkEmailCompose: React.FC<BulkEmailComposeProps> = ({
    isOpen,
    onClose,
    contactIds,
    listId,
    importedCount,
}) => {
    const [subject, setSubject] = useState('');
    const [htmlContent, setHtmlContent] = useState('');
    const [plainText, setPlainText] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [results, setResults] = useState<any>(null);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!subject.trim()) {
            setError('Subject is required');
            return;
        }
        
        if (!htmlContent.trim()) {
            setError('Email content is required');
            return;
        }

        setSending(true);
        setError('');
        setSuccess('');
        setResults(null);

        try {
            const params: any = {
                subject,
                html_content: htmlContent,
                plain_text_content: plainText || undefined,
            };

            if (listId) {
                params.list_id = listId;
            } else if (contactIds.length > 0) {
                params.contact_ids = contactIds;
            } else {
                setError('No recipients selected');
                setSending(false);
                return;
            }

            const result = await contactService.sendBulkEmail(params);

            setResults(result.results);
            setSuccess(`✓ ${result.message}`);
            
            // Clear form after success
            setTimeout(() => {
                if (result.results.sent === result.results.total) {
                    // Only auto-close if all sent successfully
                    resetForm();
                    onClose();
                }
            }, 2000);

        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to send bulk email');
            console.error('Error sending bulk email:', err);
        } finally {
            setSending(false);
        }
    };

    const resetForm = () => {
        setSubject('');
        setHtmlContent('');
        setPlainText('');
        setError('');
        setSuccess('');
        setResults(null);
    };

    const handleClose = () => {
        resetForm();
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="bulk-email-overlay" onClick={handleClose}>
            <div className="bulk-email-modal" onClick={(e) => e.stopPropagation()}>
                <div className="bulk-email-header">
                    <h2>Send Bulk Email</h2>
                    <button className="close-btn" onClick={handleClose}>×</button>
                </div>

                <div className="bulk-email-info">
                    <p>📧 <strong>Recipients:</strong> {importedCount} contacts</p>
                </div>

                {error && <div className="error-message">{error}</div>}
                {success && <div className="success-message">{success}</div>}

                {results && !sending && (
                    <div className="send-results">
                        <div className="result-item success-result">
                            <span className="result-label">✓ Sent:</span>
                            <span className="result-count">{results.sent}/{results.total}</span>
                        </div>
                        {results.failed > 0 && (
                            <div className="result-item failed-result">
                                <span className="result-label">✗ Failed:</span>
                                <span className="result-count">{results.failed}</span>
                            </div>
                        )}
                        {results.errors && results.errors.length > 0 && (
                            <div className="errors-list">
                                <p className="errors-title">Errors:</p>
                                <ul>
                                    {results.errors.slice(0, 5).map((err: any, idx: number) => (
                                        <li key={idx}>
                                            <strong>{err.email}</strong>: {err.error}
                                        </li>
                                    ))}
                                    {results.errors.length > 5 && (
                                        <li className="more-errors">
                                            ... and {results.errors.length - 5} more
                                        </li>
                                    )}
                                </ul>
                            </div>
                        )}
                    </div>
                )}

                {!results && (
                    <form onSubmit={handleSend} className="bulk-email-form">
                        <div className="form-group">
                            <label htmlFor="subject">Email Subject *</label>
                            <input
                                id="subject"
                                type="text"
                                value={subject}
                                onChange={(e) => setSubject(e.target.value)}
                                placeholder="e.g., Special Offer for Our Customers"
                                disabled={sending}
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="htmlContent">Email Content (HTML) *</label>
                            <textarea
                                id="htmlContent"
                                value={htmlContent}
                                onChange={(e) => setHtmlContent(e.target.value)}
                                placeholder="<html><body><h1>Hello</h1><p>Your message here...</p></body></html>"
                                rows={8}
                                disabled={sending}
                            />
                            <small>Use variables: {'{{first_name}}, {{last_name}}, {{email}}'} for personalization</small>
                        </div>

                        <div className="form-group">
                            <label htmlFor="plainText">Plain Text Version (Optional)</label>
                            <textarea
                                id="plainText"
                                value={plainText}
                                onChange={(e) => setPlainText(e.target.value)}
                                placeholder="Plain text version of your email"
                                rows={6}
                                disabled={sending}
                            />
                        </div>

                        <div className="bulk-email-actions">
                            <button
                                type="submit"
                                className="btn-primary"
                                disabled={sending}
                            >
                                {sending ? 'Sending...' : 'Send to All'}
                            </button>
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={handleClose}
                                disabled={sending}
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
};

export default BulkEmailCompose;
