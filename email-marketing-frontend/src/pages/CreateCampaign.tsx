import React, { useState, useEffect } from 'react';
import { useHistory, useLocation, Link } from 'react-router-dom';
import { emailService } from '../services/emailService';
import { campaignService } from '../services/campaignService';
import { contactService } from '../services/contactService';
import { templateService } from '../services/templateService';
import { EmailTemplate } from '../types';
import { buildCampaignPreviewHtml } from '../utils/emailPlainText';
import {
    applyAutoFixSuggestions,
    ContactImportSummary,
    importValidatedContactFile,
    validateContactImportFile,
} from '../utils/contactImportFlow';
import ValidationReportComponent from '../components/ValidationReport';
import { ValidationReport, isValidEmailFormat } from '../services/emailValidator';
import '../styles/campaigns.css';
import '../styles/validation-report.css';

interface ContactList {
    id: number;
    name: string;
    description?: string;
    contact_count?: number;
}

const CreateCampaign: React.FC = () => {
    const [formData, setFormData] = useState({
        name: '',
        subject: '',
        preview_text: '',
        from_email: '',
        from_name: '',
        reply_to: '',
        scheduled_at: '',
        list_ids: [] as number[],
    });
    const [recipientMode, setRecipientMode] = useState<'single' | 'bulk'>('bulk');
    const [singleEmail, setSingleEmail] = useState('');
    const [singleName, setSingleName] = useState('');
    const [importFile, setImportFile] = useState<File | null>(null);
    const [importing, setImporting] = useState(false);
    const [importProgress, setImportProgress] = useState('');
    const [validationProgress, setValidationProgress] = useState(0);
    const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
    const [showValidationReport, setShowValidationReport] = useState(false);
    const [importSummary, setImportSummary] = useState<ContactImportSummary | null>(null);
    const [importError, setImportError] = useState('');
    const [htmlContent, setHtmlContent] = useState('');
    const [plainText, setPlainText] = useState(
        'Dear Sir/Madam,\n\nI hope this email finds you well. I wanted to reach out regarding Pegasos database and lead generation services.\n\nRegards,\nGunaseelan'
    );
    const [inboxPriority, setInboxPriority] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [contactLists, setContactLists] = useState<ContactList[]>([]);
    const [loadingLists, setLoadingLists] = useState(true);
    const [importedContactIds, setImportedContactIds] = useState<number[]>([]);
    const [templates, setTemplates] = useState<EmailTemplate[]>([]);
    const [loadingTemplates, setLoadingTemplates] = useState(true);
    const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
    const [showPreview, setShowPreview] = useState(false);
    const history = useHistory();
    const location = useLocation();

    useEffect(() => {
        fetchContactLists();
        fetchTemplates();
        fetchEmailDefaults();
    }, []);

    const fetchEmailDefaults = async () => {
        try {
            const settings = await emailService.getSettings();
            const fromEmail = (settings.from_email || '').trim();
            const fromName = (settings.from_name || '').trim();
            setFormData((prev) => ({
                ...prev,
                from_email: prev.from_email || fromEmail,
                from_name: prev.from_name || fromName,
                reply_to: prev.reply_to || fromEmail,
            }));
        } catch {
            /* settings optional until configured */
        }
    };

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const contactIdsParam = params.get('contact_ids');

        if (contactIdsParam) {
            const parsedIds = contactIdsParam
                .split(',')
                .map((id) => Number(id.trim()))
                .filter((id) => !Number.isNaN(id));
            setImportedContactIds(parsedIds);
        }
    }, [location.search]);

    const fetchContactLists = async () => {
        try {
            setLoadingLists(true);
            const lists = await contactService.getContactLists();
            setContactLists(lists);
        } catch (err: any) {
            console.error('Failed to fetch contact lists:', err);
        } finally {
            setLoadingLists(false);
        }
    };

    const fetchTemplates = async () => {
        try {
            setLoadingTemplates(true);
            const { templates } = await templateService.getTemplates();
            setTemplates(templates);
        } catch (err: any) {
            console.error('Failed to fetch templates:', err);
        } finally {
            setLoadingTemplates(false);
        }
    };

    const handleTemplateSelect = async (templateId: number | null) => {
        setSelectedTemplateId(templateId);
        if (templateId === null) return;

        const selectedTemplate = templates.find((t) => t.id === templateId);
        if (selectedTemplate) {
            // Auto-populate form fields from template
            setFormData((prev) => ({
                ...prev,
                subject: selectedTemplate.subject || prev.subject,
            }));
            setHtmlContent(selectedTemplate.html_content);
            setPlainText(selectedTemplate.plain_text_content || '');
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const { name: fieldName, value } = e.target;
        setFormData((prev) => {
            const next = { ...prev, [fieldName]: value };
            if (fieldName === 'from_email') {
                const previousFrom = prev.from_email.trim();
                const previousReply = prev.reply_to.trim();
                if (!previousReply || previousReply === previousFrom) {
                    next.reply_to = value;
                }
            }
            return next;
        });
    };

    const handleListChange = (listId: number) => {
        setFormData((prev) => {
            const newListIds = prev.list_ids.includes(listId)
                ? prev.list_ids.filter((id) => id !== listId)
                : [...prev.list_ids, listId];
            return { ...prev, list_ids: newListIds };
        });
    };

    const handleSingleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSingleEmail(e.target.value);
    };

    const handleSingleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSingleName(e.target.value);
    };

    const handleImportFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0] ?? null;
        setImportError('');
        setImportSummary(null);
        setValidationReport(null);
        setShowValidationReport(false);
        setImportProgress('');
        setValidationProgress(0);
        setImportFile(file);

        if (!file) {
            return;
        }

        try {
            const report = await validateContactImportFile(file, (message, percent) => {
                setImportProgress(message);
                if (percent !== undefined) {
                    setValidationProgress(percent);
                }
            });
            setValidationReport(report);
            setImportProgress('');
            setValidationProgress(0);
        } catch (err: any) {
            setImportError(err.message || 'Failed to validate import file');
            setImportFile(null);
            setImportProgress('');
            setValidationProgress(0);
        }
    };

    const handleAutoFixSuggestions = (
        correctedEmails: Array<{ original: string; corrected: string; rowNumber: number }>,
    ) => {
        if (!validationReport) {
            return;
        }
        setValidationReport(applyAutoFixSuggestions(validationReport, correctedEmails));
    };

    const handleImportContacts = async () => {
        if (!importFile || !validationReport) {
            setImportError('Please choose a CSV or Excel file and wait for validation to finish.');
            return;
        }

        if (validationReport.validEmails === 0) {
            setImportError('No valid emails to import. Review the validation report and fix errors.');
            setShowValidationReport(true);
            return;
        }

        setImporting(true);
        setImportError('');
        setImportProgress('Importing validated contacts...');
        try {
            const listId = formData.list_ids.length > 0 ? formData.list_ids[0] : undefined;
            const result = await importValidatedContactFile(validationReport, listId);

            if (!result?.summary) {
                throw new Error('Contact import response was invalid.');
            }

            setImportSummary(result.summary);
            setImportedContactIds(result.summary.contact_ids || []);
            setShowValidationReport(false);
            setImportProgress('');
        } catch (err: any) {
            setImportError(err.response?.data?.error || err.message || 'Contact import failed.');
            setImportProgress('');
        } finally {
            setImporting(false);
        }
    };

    const hasRecipientSelection =
        recipientMode === 'single'
            ? !!singleEmail.trim()
            : formData.list_ids.length > 0 || importedContactIds.length > 0;

    const shouldShowPreview = showPreview && (!!htmlContent.trim() || !!plainText.trim());
    const previewDocument = buildCampaignPreviewHtml(
        htmlContent,
        plainText,
        inboxPriority,
        formData.from_name,
    );

    const canSend =
        !!formData.name.trim() &&
        !!formData.subject.trim() &&
        !!htmlContent.trim() &&
        !!formData.from_email.trim() &&
        hasRecipientSelection;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setLoading(true);

        try {
            if (!formData.name.trim() || !formData.subject.trim() || !htmlContent.trim() || !formData.from_email.trim()) {
                setError('Please fill in all required fields before sending.');
                setLoading(false);
                return;
            }

            if (!hasRecipientSelection) {
                setError(
                    recipientMode === 'single'
                        ? 'Please enter a recipient email address for Single Email.'
                        : 'Please select at least one contact list or import recipients from CSV/Excel.'
                );
                setLoading(false);
                return;
            }

            let contactIds: number[] = [];

            if (recipientMode === 'single') {
                const normalizedEmail = singleEmail.trim().toLowerCase();
                if (!isValidEmailFormat(normalizedEmail)) {
                    setError('Please enter a valid recipient email address (any domain is accepted).');
                    setLoading(false);
                    return;
                }
                const contact = await contactService.createContact({
                    email: normalizedEmail,
                    name: singleName.trim(),
                });

                if (!contact?.id) {
                    throw new Error('Failed to create recipient contact.');
                }

                contactIds = [contact.id];
            } else {
                contactIds = importedContactIds;
            }

            const campaignPayload: any = {
                name: formData.name,
                subject: formData.subject,
                preview_text: formData.preview_text,
                from_email: formData.from_email,
                from_name: formData.from_name,
                reply_to: formData.reply_to.trim() || formData.from_email.trim(),
                inbox_priority: inboxPriority,
                content: {
                    html_content: htmlContent,
                    plain_text_content: plainText,
                },
            };

            if (recipientMode === 'bulk') {
                campaignPayload.list_ids = formData.list_ids;
                campaignPayload.contact_ids = contactIds;
            } else {
                campaignPayload.contact_ids = contactIds;
            }

            if (formData.scheduled_at) {
                campaignPayload.scheduled_at = formData.scheduled_at;
            }

            const campaign = await campaignService.createCampaign(campaignPayload);

            if (!campaign?.id) {
                throw new Error('Campaign created but no ID returned.');
            }

            const recipientTotal = campaign.delivery_summary?.total ?? 0;
            if (recipientMode === 'bulk' && importedContactIds.length > 0 && recipientTotal === 0) {
                throw new Error(
                    'No recipients were added to this campaign. Re-import your contacts or select a contact list, then try again.'
                );
            }
            if (recipientMode === 'bulk' && importedContactIds.length > recipientTotal) {
                setError(
                    `Warning: only ${recipientTotal} of ${importedContactIds.length} imported contacts were added. ` +
                        'Some rows may have been skipped during import.'
                );
            }

            const shouldSchedule = formData.scheduled_at
                ? new Date(formData.scheduled_at).getTime() > Date.now()
                : false;

            let pendingRemaining = 0;

            if (shouldSchedule) {
                await campaignService.scheduleCampaign(campaign.id, formData.scheduled_at);
                setSuccess(`Campaign scheduled successfully for ${new Date(formData.scheduled_at).toLocaleString()}`);
            } else {
                const sendResult = await campaignService.sendCampaign(campaign.id);
                pendingRemaining = sendResult.result?.pending_remaining ?? 0;
                let message = sendResult.message || 'Campaign sent successfully.';
                if (sendResult.async) {
                    message =
                        `${message}\n\nSending continues in the background. ` +
                        'Open analytics to watch delivery progress live — do not click Send again.';
                } else {
                    const note = sendResult.result?.deliverability_note;
                    if (note) {
                        message = `${message}\n\n${note}`;
                    }
                    if (pendingRemaining > 0) {
                        message = `${message}\n\n${pendingRemaining} recipient(s) still pending — open the campaign and click Send again.`;
                    }
                }
                setSuccess(message);
            }

            setTimeout(() => {
                if (!shouldSchedule && campaign?.id) {
                    history.push(`/campaigns/${campaign.id}/analytics`);
                } else {
                    history.push('/campaigns');
                }
            }, shouldSchedule ? 1500 : 800);
        } catch (err: any) {
            let errorMessage = 'Failed to send campaign';

            if (err.response?.data) {
                const data = err.response.data;
                if (data.error) {
                    errorMessage = data.error;
                } else if (data.message) {
                    errorMessage = data.message;
                } else if (data.detail) {
                    errorMessage = data.detail;
                } else if (typeof data === 'object' && !Array.isArray(data) && data !== null) {
                    const errors: string[] = [];
                    for (const [field, messages] of Object.entries(data)) {
                        if (field === 'result') {
                            continue;
                        }
                        if (Array.isArray(messages)) {
                            errors.push(`${field}: ${messages[0]}`);
                        } else if (typeof messages === 'object' && messages !== null) {
                            for (const [nestedField, nestedMessages] of Object.entries(messages)) {
                                if (Array.isArray(nestedMessages)) {
                                    errors.push(`${field}.${nestedField}: ${nestedMessages[0]}`);
                                } else if (nestedMessages) {
                                    errors.push(`${field}: ${nestedMessages}`);
                                }
                            }
                        } else if (messages) {
                            errors.push(`${field}: ${messages}`);
                        }
                    }
                    if (errors.length > 0) {
                        errorMessage = errors.join('\n');
                    }
                }
            } else if (err.message) {
                errorMessage = err.message;
            }

            if (
                err.code === 'ECONNABORTED' ||
                String(err.message || '').toLowerCase().includes('timeout')
            ) {
                errorMessage =
                    'The send request timed out, but emails may still be sending in the background. ' +
                    'Open Campaigns → Analytics for this campaign to check live progress. ' +
                    'Do not click Send again unless analytics shows failed/pending recipients.';
            }

            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={`create-campaign-page ${shouldShowPreview ? 'show-preview' : ''}`}>
            <div className="create-campaign-header">
                <div>
                    <h1>Create Campaign</h1>
                </div>
            </div>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <div className="create-campaign-wrapper">
                {/* Left: Form Section */}
                <div className="campaign-form-section">
                    <form onSubmit={handleSubmit} className="campaign-form">
                        {/* Campaign Details */}
                        <fieldset>
                            <legend>Campaign Details</legend>

                            <div className="form-group">
                                <label htmlFor="name">Campaign Name *</label>
                                <input
                                    id="name"
                                    name="name"
                                    type="text"
                                    value={formData.name}
                                    onChange={handleChange}
                                    required
                                    placeholder="e.g., Spring Newsletter"
                                />
                            </div>

                            <div className="form-row">
                                <div className="form-group">
                                    <label htmlFor="subject">Email Subject *</label>
                                    <input
                                        id="subject"
                                        name="subject"
                                        type="text"
                                        value={formData.subject}
                                        onChange={handleChange}
                                        required
                                        placeholder="e.g., Check out our latest updates"
                                    />
                                </div>
                                <div className="form-group">
                                    <label htmlFor="preview_text">Preview Text</label>
                                    <input
                                        id="preview_text"
                                        name="preview_text"
                                        type="text"
                                        value={formData.preview_text}
                                        onChange={handleChange}
                                        placeholder="Preview text shown in email client"
                                    />
                                </div>
                            </div>
                        </fieldset>

                        {/* Templates */}
                        <fieldset>
                            <legend>Templates</legend>
                            <div className="form-group">
                                <label htmlFor="templateSelect">Select a Template (Optional)</label>
                                {loadingTemplates ? (
                                    <p>Loading templates...</p>
                                ) : (
                                    <div>
                                        <select
                                            id="templateSelect"
                                            value={selectedTemplateId ?? ''}
                                            onChange={(e) => handleTemplateSelect(e.target.value ? Number(e.target.value) : null)}
                                            className="form-input"
                                        >
                                            <option value="">-- No Template --</option>
                                            {templates.map((template) => (
                                                <option key={template.id} value={template.id}>
                                                    {template.name} {template.category ? `(${template.category})` : ''}
                                                </option>
                                            ))}
                                        </select>
                                        <small>
                                            Select a template to auto-populate the email content. You can edit all fields after selection.
                                        </small>
                                    </div>
                                )}
                                {selectedTemplateId && (
                                    <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
                                        <p style={{ margin: '0 0 5px 0', fontSize: '0.9em' }}>
                                            ✓ Template "{templates.find((t) => t.id === selectedTemplateId)?.name}" selected and content loaded.
                                            You can edit the content below.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </fieldset>

                        {/* Sender Info */}
                        <fieldset>
                            <legend>Sender Information</legend>

                            <div className="form-row">
                                <div className="form-group">
                                    <label htmlFor="from_email">From Email *</label>
                                    <input
                                        id="from_email"
                                        name="from_email"
                                        type="email"
                                        value={formData.from_email}
                                        onChange={handleChange}
                                        required
                                        placeholder="sender@example.com"
                                    />
                                </div>
                                <div className="form-group">
                                    <label htmlFor="from_name">From Name</label>
                                    <input
                                        id="from_name"
                                        name="from_name"
                                        type="text"
                                        value={formData.from_name}
                                        onChange={handleChange}
                                        placeholder={inboxPriority ? 'e.g., Guna (personal name)' : 'Your Company Name'}
                                    />
                                    {inboxPriority && (
                                        <small className="field-hint">
                                            Use a personal name (e.g. Guna), not a company name — Gmail is more likely
                                            to show Primary inbox when the sender looks like a person.
                                        </small>
                                    )}
                                </div>
                            </div>

                            <div className="form-group">
                                <label htmlFor="reply_to">Reply-To Email</label>
                                <input
                                    id="reply_to"
                                    name="reply_to"
                                    type="email"
                                    value={formData.reply_to}
                                    onChange={handleChange}
                                    placeholder={formData.from_email || 'Same as From email'}
                                />
                                <small className="field-hint">
                                    Replies go here. Use the same address as <strong>From Email</strong>{' '}
                                    ({formData.from_email || 'e.g. gunaseelan@pegasos.in'}) — do not use your
                                    personal Gmail login. Leave blank to match From Email automatically.
                                </small>
                            </div>
                        </fieldset>

                        {/* Recipients */}
                        <fieldset>
                            <legend>Recipients</legend>
                            <div className="recipient-mode-switch">
                                <button
                                    type="button"
                                    className={`recipient-mode-btn ${recipientMode === 'single' ? 'active' : ''}`}
                                    onClick={() => setRecipientMode('single')}
                                >
                                    Single Email
                                </button>
                                <button
                                    type="button"
                                    className={`recipient-mode-btn ${recipientMode === 'bulk' ? 'active' : ''}`}
                                    onClick={() => setRecipientMode('bulk')}
                                >
                                    Bulk Emails
                                </button>
                            </div>

                            {recipientMode === 'single' ? (
                                <div className="single-recipient-section">
                                    <div className="form-group">
                                        <label htmlFor="single_email">Recipient Email *</label>
                                        <input
                                            id="single_email"
                                            type="email"
                                            value={singleEmail}
                                            onChange={handleSingleEmailChange}
                                            required
                                            placeholder="recipient@example.com"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label htmlFor="single_name">Recipient Name</label>
                                        <input
                                            id="single_name"
                                            type="text"
                                            value={singleName}
                                            onChange={handleSingleNameChange}
                                            placeholder="Customer name (optional)"
                                        />
                                    </div>
                                    <p className="selected-info">
                                        This email will be sent directly to a single recipient. A contact record will be created or updated automatically.
                                    </p>
                                </div>
                            ) : (
                                <div className="bulk-recipient-section">
                                    {loadingLists ? (
                                        <p>Loading contact lists...</p>
                                    ) : contactLists.length > 0 ? (
                                        <div className="contact-lists-selector">
                                            {contactLists.map((list) => (
                                                <label key={list.id} className="list-checkbox">
                                                    <input
                                                        type="checkbox"
                                                        checked={formData.list_ids.includes(list.id)}
                                                        onChange={() => handleListChange(list.id)}
                                                    />
                                                    <div className="checkbox-content">
                                                        <div className="list-name">{list.name}</div>
                                                        <div className="list-info">
                                                            {list.contact_count} contacts
                                                            {list.description && ` • ${list.description}`}
                                                        </div>
                                                    </div>
                                                </label>
                                            ))}
                                        </div>
                                    ) : (
                                        <p style={{ color: '#e74c3c' }}>
                                            No contact lists found.{' '}
                                            <Link to="/contacts" style={{ color: 'var(--brand)' }}>
                                                Create one first
                                            </Link>
                                        </p>
                                    )}

                                    <div className="import-section">
                                        <p>
                                            Import recipients directly from CSV or Excel. All valid email domains are
                                            accepted (Gmail, Yahoo, Outlook, and business domains such as pegasos.in,
                                            company.co.in, etc.). Validation and duplicate checks match the Contacts module.
                                        </p>
                                        <div className="form-row">
                                            <div className="form-group" style={{ flex: 1 }}>
                                                <label htmlFor="import_file">Import Contacts</label>
                                                <input
                                                    id="import_file"
                                                    type="file"
                                                    accept=".csv,.xlsx,.xls,.txt"
                                                    onChange={handleImportFileChange}
                                                />
                                                <small className="field-hint">
                                                    Supported: CSV, Excel (.xlsx, .xls), TXT. Include an &quot;email&quot; column.
                                                </small>
                                            </div>
                                            <div className="form-group import-actions">
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        if (validationReport && validationReport.invalidEmails > 0) {
                                                            setShowValidationReport(true);
                                                            return;
                                                        }
                                                        handleImportContacts();
                                                    }}
                                                    disabled={
                                                        importing ||
                                                        !importFile ||
                                                        !validationReport ||
                                                        validationReport.validEmails === 0
                                                    }
                                                    className="btn-primary"
                                                >
                                                    {importing
                                                        ? 'Importing...'
                                                        : validationReport && validationReport.invalidEmails > 0
                                                          ? 'Review validation'
                                                          : 'Import Contacts'}
                                                </button>
                                            </div>
                                        </div>
                                        {importProgress && (
                                            <div className="import-progress">
                                                <div className="info-message">{importProgress}</div>
                                                {validationProgress > 0 && validationProgress < 100 && (
                                                    <div className="validation-progress-bar">
                                                        <div
                                                            className="validation-progress-fill"
                                                            style={{ width: `${validationProgress}%` }}
                                                        />
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        {validationReport && !importSummary && (
                                            <p className="selected-info">
                                                Validation: {validationReport.validEmails} valid,{' '}
                                                {validationReport.invalidEmails} invalid,{' '}
                                                {validationReport.duplicateEmails} duplicate(s)
                                            </p>
                                        )}
                                        {showValidationReport && validationReport && (
                                            <ValidationReportComponent
                                                report={validationReport}
                                                onAutoFixSuggestions={handleAutoFixSuggestions}
                                                onProceedWithImport={handleImportContacts}
                                                onClose={() => setShowValidationReport(false)}
                                            />
                                        )}
                                        {importError && <div className="error-message">{importError}</div>}
                                        {importSummary && (
                                            <div className="import-summary">
                                                <p>
                                                    Imported {(importSummary.contact_ids?.length ?? 0)} recipient(s):{' '}
                                                    {importSummary.created} created, {importSummary.updated} updated,{' '}
                                                    {importSummary.skipped} skipped.
                                                </p>
                                                {(importSummary.data_rows_in_sheet ?? 0) > 0 &&
                                                    (importSummary.data_rows_in_sheet ?? 0) !== (importSummary.contact_ids?.length ?? 0) && (
                                                    <p className="field-hint">
                                                        File has {importSummary.data_rows_in_sheet ?? 0} data row(s)
                                                        {importSummary.sheet_rows ? ` (${importSummary.sheet_rows} rows including header)` : ''}.
                                                        {(importSummary.duplicate_count ?? 0) > 0 &&
                                                            ` ${importSummary.duplicate_count} duplicate email(s) in file.`}
                                                        {(importSummary.invalid_count ?? 0) > 0 &&
                                                            ` ${importSummary.invalid_count} invalid/empty row(s).`}
                                                        {(importSummary.blank_rows_in_sheet ?? 0) > 0 &&
                                                            ` ${importSummary.blank_rows_in_sheet} blank row(s) at end of sheet.`}
                                                    </p>
                                                )}
                                                {importSummary.errors.length > 0 && (
                                                    <div className="import-errors">
                                                        <strong>Rows not imported:</strong>
                                                        <ul>
                                                            {importSummary.errors.slice(0, 10).map((error) => (
                                                                <li key={`${error.row}-${error.email}`}>
                                                                    Row {error.row}: {error.email} — {error.error}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {formData.list_ids.length > 0 && (
                                            <p className="selected-info">
                                                Selected: {formData.list_ids.length} list(s) with{' '}
                                                {contactLists
                                                    .filter((l) => formData.list_ids.includes(l.id))
                                                    .reduce((sum, l) => sum + (l.contact_count ?? 0), 0)}{' '}
                                                total contacts
                                            </p>
                                        )}
                                        {importedContactIds.length > 0 && (
                                            <p className="selected-info">
                                                Imported recipients: {importedContactIds.length}
                                            </p>
                                        )}
                                        {(formData.list_ids.length > 0 || importedContactIds.length > 0) && (
                                            <p className="selected-info">
                                                Total recipients: {
                                                    contactLists
                                                        .filter((l) => formData.list_ids.includes(l.id))
                                                        .reduce((sum, l) => sum + (l.contact_count ?? 0), 0) + importedContactIds.length
                                                }
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </fieldset>

                        {/* Schedule */}
                        <fieldset>
                            <legend>Schedule</legend>
                            <div className="form-group">
                                <label htmlFor="scheduled_at">Send Date & Time</label>
                                <input
                                    id="scheduled_at"
                                    name="scheduled_at"
                                    type="datetime-local"
                                    value={formData.scheduled_at}
                                    onChange={handleChange}
                                    className="form-input"
                                />
                                <small>If you leave this blank, the campaign will send immediately.</small>
                            </div>
                        </fieldset>

                        {/* Email Content */}
                        <fieldset>
                            <legend>Email Content</legend>

                            <div className="form-group">
                                <label htmlFor="htmlContent">HTML Content *</label>
                                <textarea
                                    id="htmlContent"
                                    value={htmlContent}
                                    onChange={(e) => setHtmlContent(e.target.value)}
                                    required
                                    placeholder="<html>...</html>"
                                    rows={10}
                                />
                                <small>Optional: use {'{{name}}'} or {'{{email}}'} only if you want a different message per contact.</small>
                            </div>

                            <div className="form-group preview-toggle-group">
                                <label className="checkbox-label" htmlFor="inboxPriority">
                                    <input
                                        id="inboxPriority"
                                        type="checkbox"
                                        checked={inboxPriority}
                                        onChange={(e) => setInboxPriority(e.target.checked)}
                                    />
                                    <span>
                                        <strong>Inbox Priority</strong> — recipients receive a plain personal email
                                        (text only, no marketing HTML). Content is taken from your plain text field or
                                        converted from HTML, including phone and website.
                                    </span>
                                </label>
                                {inboxPriority && (
                                    <small className="field-hint">
                                        Best for Gmail Primary inbox. Sends as <strong>plain personal email</strong>{' '}
                                        (no HTML/marketing layout) while keeping your message content. Preview shows
                                        HTML for editing only. Use a personal From name, simple subject, and stagger
                                        sends — not every recipient will land in Primary (Gmail decides per person).
                                    </small>
                                )}
                                {!inboxPriority && (
                                    <small className="field-hint">
                                        Marketing HTML mode: uses your full HTML design but mail may land in Promotions
                                        or All Mail instead of Primary inbox.
                                    </small>
                                )}
                            </div>

                            <div className="form-group preview-toggle-group">
                                <label className="checkbox-label" htmlFor="showPreview">
                                    <input
                                        id="showPreview"
                                        type="checkbox"
                                        checked={showPreview}
                                        onChange={(e) => setShowPreview(e.target.checked)}
                                    />
                                    <span>Show Preview</span>
                                </label>
                            </div>

                            <div className="form-group">
                                <label htmlFor="plainText">Plain text content (recommended for Gmail Primary inbox)</label>
                                <textarea
                                    id="plainText"
                                    value={plainText}
                                    onChange={(e) => setPlainText(e.target.value)}
                                    placeholder={'Dear Sir/Madam,\n\nYour message here.\n\nRegards,\nYour name'}
                                    rows={10}
                                />
                                <small className="field-hint">
                                    Optional if HTML is filled in above. With Inbox Priority, Pegasos uses the
                                    most complete version (HTML is converted to plain text so phone and website
                                    in your HTML signature are included).
                                </small>
                            </div>
                        </fieldset>

                        <div className="form-actions">
                            <button type="submit" disabled={loading || !canSend} className="btn-primary">
                                {loading ? 'Sending...' : 'Send Campaign'}
                            </button>
                            <button
                                type="button"
                                onClick={() => history.push('/campaigns')}
                                className="btn-secondary"
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>

                {/* Right: Live Preview Section */}
                {shouldShowPreview && (
                    <div className="campaign-preview-section">
                        <div className="preview-container">
                            <div className="preview-frame">
                                <div className="email-wrapper">
                                    <div className="email-header">
                                        <div className="email-subject">{formData.subject || 'Email Subject'}</div>
                                        <div className="email-from">From: {formData.from_email}</div>
                                        {formData.from_name && <div className="email-from-name">({formData.from_name})</div>}
                                        {formData.preview_text && (
                                            <div className="email-preview">{formData.preview_text}</div>
                                        )}
                                    </div>
                                    <div className="email-content">
                                        <p className="inbox-plain-preview-label">
                                            {previewDocument.mode === 'inbox-plain'
                                                ? 'Inbox Priority preview (plain email recipients will receive)'
                                                : previewDocument.mode === 'designed'
                                                  ? 'Designed HTML preview (marketing mode — may land in Promotions)'
                                                  : 'Email preview'}
                                        </p>
                                        <div className="preview-iframe-wrap">
                                            <iframe
                                                key={previewDocument.html}
                                                srcDoc={previewDocument.html}
                                                title="Email Preview"
                                                className="preview-iframe preview-iframe--auto"
                                                sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
                                                scrolling="yes"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CreateCampaign;
