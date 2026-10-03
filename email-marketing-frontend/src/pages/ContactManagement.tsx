import React, { useEffect, useState } from 'react';
import { useHistory } from 'react-router-dom';
import api from '../services/api';
import PageShell from '../components/ui/PageShell';
import ValidationReportComponent from '../components/ValidationReport';
import { ValidationReport } from '../services/emailValidator';
import {
    applyAutoFixSuggestions,
    importValidatedContactFile,
    validateContactImportFile,
} from '../utils/contactImportFlow';
import '../styles/contacts.css';
import '../styles/validation-report.css';

interface Contact {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
    subscribed: boolean;
    tags: string[];
    name?: string;
    is_subscribed?: boolean;
}



interface ImportResult {
    created: number;
    updated: number;
    skipped: number;
    total: number;
    contact_ids?: number[];
    errors: Array<{ row: number; email: string; error: string }>;
}

interface ContactListItem {
    id: number;
    name: string;
    description: string;
    contact_count: number;
}

interface ImportHistoryEntry {
    id: number;
    filename: string;
    file_type: string;
    status: string;
    total_rows: number;
    valid_count: number;
    invalid_count: number;
    duplicate_count: number;
    created_count: number;
    updated_count: number;
    skipped_count: number;
    contact_list: string | null;
    started_at: string;
    completed_at: string | null;
    error_count: number;
}

const ContactManagement: React.FC = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [contacts, setContacts] = useState<Contact[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // Form states
    const [showAddContactForm, setShowAddContactForm] = useState(false);
    const [showImportCSV, setShowImportCSV] = useState(false);
    const [importErrors, setImportErrors] = useState<Array<{ row: number; email: string; error: string }>>([]);

    const [newContact, setNewContact] = useState({
        email: '',
        name: '',
        is_subscribed: true
    });

    const [csvFile, setCsvFile] = useState<File | null>(null);
    const [csvListId, setCsvListId] = useState<number | null>(null);
    const [contactLists, setContactLists] = useState<ContactListItem[]>([]);
    const [newListName, setNewListName] = useState('');
    const [showCreateList, setShowCreateList] = useState(false);
    const [importProgress, setImportProgress] = useState('');
    const [validationProgress, setValidationProgress] = useState(0);
    const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
    const [showValidationReport, setShowValidationReport] = useState(false);
    const [importHistory, setImportHistory] = useState<ImportHistoryEntry[]>([]);
    const history = useHistory();

    useEffect(() => {
        fetchContacts();
        fetchContactLists();
        fetchImportHistory();
    }, []);

    const fetchImportHistory = async () => {
        try {
            const response = await api.get('/campaigns/contacts/import/history/');
            setImportHistory(response.data.history || []);
        } catch {
            // Non-fatal
        }
    };

    const fetchContactLists = async () => {
        try {
            const response = await api.get('/campaigns/contact-lists/');
            setContactLists(response.data);
        } catch {
            // Non-fatal — lists section stays empty
        }
    };

    const handleCreateList = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newListName.trim()) return;
        try {
            await api.post('/campaigns/contact-lists/', { name: newListName.trim() });
            setNewListName('');
            setShowCreateList(false);
            setSuccess('Contact list created');
            fetchContactLists();
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to create list');
        }
    };

    const fetchContacts = async () => {
        try {
            setLoading(true);
            const response = await api.get('/campaigns/contacts/');
            setContacts(response.data);
            setError('');
        } catch (err: any) {
            setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to load contacts');
        } finally {
            setLoading(false);
        }
    };



    const handleAddContact = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            setError('');
            setSuccess('');

            if (!newContact.email) {
                setError('Email is required');
                return;
            }

            await api.post('/campaigns/contacts/create/', {
                email: newContact.email,
                name: newContact.name,
                is_subscribed: newContact.is_subscribed
            });

            setSuccess('Contact added successfully!');
            setNewContact({ email: '', name: '', is_subscribed: true });
            setShowAddContactForm(false);
            fetchContacts();
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to add contact');
        }
    };

    const handleDeleteContact = async (id: number) => {
        if (window.confirm('Delete this contact?')) {
            try {
                setError('');
                setSuccess('');
                await api.delete(`/campaigns/contacts/${id}/`);
                setSuccess('Contact deleted successfully!');
                fetchContacts();
            } catch (err: any) {
                setError(err.response?.data?.error || 'Failed to delete contact');
            }
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setError('');
        setValidationReport(null);
        setValidationProgress(0);
        setCsvFile(file);

        try {
            const report = await validateContactImportFile(file, (message, percent) => {
                setImportProgress(message);
                if (percent !== undefined) {
                    setValidationProgress(percent);
                }
            });

            setValidationReport(report);
            setShowValidationReport(false);
            setImportProgress('');
            setValidationProgress(0);
        } catch (err: any) {
            setError(err.message || `Error reading file: ${err.message}`);
            setCsvFile(null);
            setImportProgress('');
            setValidationProgress(0);
        }
    };

    const handleAutoFixSuggestions = (correctedEmails: Array<{ original: string; corrected: string; rowNumber: number }>) => {
        if (!validationReport) return;
        setValidationReport(applyAutoFixSuggestions(validationReport, correctedEmails));
        setSuccess(`Auto-fixed ${correctedEmails.length} email address(es)`);
    };

    const handleProceedWithImport = async () => {
        if (!csvFile || !validationReport || validationReport.validEmails === 0) {
            setError('No valid emails to import');
            return;
        }

        setShowValidationReport(false);
        setImportProgress('Importing validated contacts...');

        try {
            const result = await importValidatedContactFile(validationReport, csvListId || undefined);
            const importResult = result.summary;
            const importedIds = importResult.contact_ids || [];

            setSuccess(
                `Import completed! Created: ${importResult.created}, Updated: ${importResult.updated}, Skipped: ${importResult.skipped}`
            );

            // Clear form
            setCsvFile(null);
            setCsvListId(null);
            setValidationReport(null);
            setImportProgress('');
            setShowImportCSV(false);

            await fetchContacts();
            await fetchImportHistory();

            // Redirect to campaign creation if there are imported contacts
            if (importedIds.length > 0) {
                const params = new URLSearchParams();
                params.set('contact_ids', importedIds.join(','));
                history.push(`/campaigns/create?${params.toString()}`);
            }
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to import contacts');
            setImportProgress('');
        }
    };

    const handleImportCSV = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            setError('');
            setSuccess('');
            setImportErrors([]);

            if (!csvFile) {
                setError('Please select a CSV or Excel file');
                return;
            }

            setImportProgress('Uploading and processing...');

            const formData = new FormData();
            formData.append('file', csvFile);
            if (csvListId) {
                formData.append('list_id', String(csvListId));
            }

            const response = await api.post('/campaigns/contacts/import/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const result: ImportResult = response.data.summary;
            const importedIds = result.contact_ids || [];
            
            setSuccess(
                `Import completed! Created: ${result.created}, Updated: ${result.updated}, Skipped: ${result.skipped}`
            );

            setImportErrors(result.errors || []);
            
            // Clear CSV form
            setCsvFile(null);
            setCsvListId(null);
            setImportProgress('');
            setShowImportCSV(false);
            
            // Refresh contacts list
            await fetchContacts();
            await fetchImportHistory();
            
            // Redirect to Campaign creation with imported contact ids
            if (importedIds.length > 0) {
                const params = new URLSearchParams();
                params.set('contact_ids', importedIds.join(','));
                history.push(`/campaigns/create?${params.toString()}`);
            }
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to import contacts');
            setImportProgress('');
        }
    };


    const handleDownloadTemplate = async () => {
        try {
            const response = await api.get('/campaigns/contacts/import-template/', {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'contact_template.csv');
            document.body.appendChild(link);
            link.click();
        } catch (err: any) {
            setError('Failed to download template');
        }
    };

    const handleExportCSV = async () => {
        try {
            const response = await api.get('/campaigns/contacts/export/', {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `contacts_${new Date().toISOString().split('T')[0]}.csv`);
            document.body.appendChild(link);
            link.click();
        } catch (err: any) {
            setError('Failed to export contacts');
        }
    };

    const filteredContacts = contacts.filter(c =>
        (c.email?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
        (c.name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
        (c.first_name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
        (c.last_name?.toLowerCase() || '').includes(searchTerm.toLowerCase())
    );

    if (loading) {
        return <div className="loading-spinner">Loading contacts…</div>;
    }

    return (
        <PageShell
            title="Contacts"
            subtitle="Manage subscribers, lists, and bulk import from CSV, Excel, or TXT."
            actions={
                <>
                    <button type="button" className="btn-primary" onClick={() => setShowAddContactForm(true)}>
                        Add contact
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => {
                        setCsvFile(null);
                        setCsvListId(null);
                        setValidationReport(null);
                        setShowImportCSV(true);
                    }}>
                        Import Contacts
                    </button>
                    <button type="button" className="btn-secondary" onClick={handleExportCSV}>
                        Export CSV
                    </button>
                </>
            }
        >
            {error && <div className="alert alert-error">{error}</div>}
            {success && <div className="alert alert-success">{success}</div>}
            {importErrors.length > 0 && (
                <div className="error-message import-errors">
                    <strong>Import skipped {importErrors.length} row(s):</strong>
                    <ul>
                        {importErrors.slice(0, 3).map((err) => (
                            <li key={`${err.row}-${err.email}`}>{`Row ${err.row} (${err.email}): ${err.error}`}</li>
                        ))}
                        {importErrors.length > 3 && <li>...and {importErrors.length - 3} more errors</li>}
                    </ul>
                </div>
            )}

            <section className="contacts-overview card-panel">
                <div className="overview-card">
                    <p className="overview-label">Subscribers</p>
                    <div className="overview-value">{contacts.length}</div>
                    <p className="overview-note">Search and manage your audience with a clean contact directory.</p>
                </div>
            </section>

            <section className="contacts-tab card-panel">
                <div className="section-header">
                    <div>
                        <h2>Contact Lists</h2>
                        <p className="section-copy">Organize contacts into lists for campaigns and drips.</p>
                    </div>
                    <button type="button" className="btn-secondary btn-small" onClick={() => setShowCreateList(true)}>
                        New list
                    </button>
                </div>
                {contactLists.length > 0 ? (
                    <div className="table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Contacts</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {contactLists.map((list) => (
                                    <tr key={list.id}>
                                        <td>{list.name}</td>
                                        <td>{list.contact_count}</td>
                                        <td>
                                            <button
                                                type="button"
                                                className="btn-ghost btn-small"
                                                onClick={() => history.push(`/contact-lists/${list.id}`)}
                                            >
                                                View
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="section-copy">No contact lists yet. Create one to group subscribers.</p>
                )}
            </section>

            <section className="contacts-tab card-panel">
                <div className="section-header">
                    <div>
                        <h2>Import History</h2>
                        <p className="section-copy">Recent contact imports with validation and import statistics.</p>
                    </div>
                </div>
                {importHistory.length > 0 ? (
                    <div className="table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>File</th>
                                    <th>Status</th>
                                    <th>Valid</th>
                                    <th>Invalid</th>
                                    <th>Duplicates</th>
                                    <th>Created</th>
                                    <th>Updated</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {importHistory.map((entry) => (
                                    <tr key={entry.id}>
                                        <td>
                                            <span className="import-filename">{entry.filename}</span>
                                            <span className="import-filetype">.{entry.file_type}</span>
                                        </td>
                                        <td>
                                            <span className={`status-badge status-${entry.status}`}>
                                                {entry.status}
                                            </span>
                                        </td>
                                        <td>{entry.valid_count}</td>
                                        <td>{entry.invalid_count}</td>
                                        <td>{entry.duplicate_count}</td>
                                        <td>{entry.created_count}</td>
                                        <td>{entry.updated_count}</td>
                                        <td>{new Date(entry.started_at).toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="section-copy">No import history yet. Import contacts to see audit logs here.</p>
                )}
            </section>

            {/* Contacts Section */}
            <section className="contacts-tab card-panel">
                    <div className="section-header">
                        <div>
                            <h2>Contact Directory</h2>
                            <p className="section-copy">Find and manage your subscriber records quickly with search and actions.</p>
                        </div>
                        <div className="contacts-summary">
                            <span>{contacts.length} contacts</span>
                        </div>
                    </div>

                    <div className="contacts-toolbar">
                        <div className="search-box">
                            <input
                                type="text"
                                placeholder="Search by email or name"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>

                    {filteredContacts.length > 0 ? (
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Email</th>
                                        <th>Name</th>
                                        <th>Status</th>
                                        <th>Tags</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredContacts.map((contact) => (
                                        <tr key={contact.id}>
                                            <td>{contact.email}</td>
                                            <td>{contact.name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim()}</td>
                                            <td>
                                                <span
                                                    className={`status-badge ${
                                                        (contact.subscribed || contact.is_subscribed) ? 'status-active' : 'status-inactive'
                                                    }`}
                                                >
                                                    {(contact.subscribed || contact.is_subscribed) ? 'Active' : 'Inactive'}
                                                </span>
                                            </td>
                                            <td>
                                                {contact.tags?.length > 0 ? (
                                                    contact.tags.map((tag) => (
                                                        <span key={tag} className="tag">
                                                            {tag}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="no-tags">—</span>
                                                )}
                                            </td>
                                            <td>
                                                <button
                                                    onClick={() => handleDeleteContact(contact.id)}
                                                    className="btn-small btn-delete"
                                                >
                                                    Delete
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="empty-state">
                            <p>No matching contacts found.</p>
                        </div>
                    )}
            </section>

            {/* Add Contact Modal */}
            {showAddContactForm && (
                <div className="modal-overlay" onClick={() => setShowAddContactForm(false)}>
                    <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Add New Contact</h2>
                            <button
                                className="close-btn"
                                onClick={() => setShowAddContactForm(false)}
                            >
                                ×
                            </button>
                        </div>
                        <form onSubmit={handleAddContact} className="form">
                            <div className="form-group">
                                <label>Email *</label>
                                <input
                                    type="email"
                                    value={newContact.email}
                                    onChange={(e) =>
                                        setNewContact({ ...newContact, email: e.target.value })
                                    }
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Name</label>
                                <input
                                    type="text"
                                    value={newContact.name}
                                    onChange={(e) =>
                                        setNewContact({ ...newContact, name: e.target.value })
                                    }
                                />
                            </div>
                            <div className="form-group">
                                <label>
                                    <input
                                        type="checkbox"
                                        checked={newContact.is_subscribed}
                                        onChange={(e) =>
                                            setNewContact({ ...newContact, is_subscribed: e.target.checked })
                                        }
                                    />
                                    Subscribed
                                </label>
                            </div>
                
                            <div className="modal-actions">
                                <button type="submit" className="btn-primary">
                                    Add Contact
                                </button>
                                <button
                                    type="button"
                                    className="btn-secondary"
                                    onClick={() => setShowAddContactForm(false)}
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Import Contacts Modal */}
            {showImportCSV && (
                <div className="modal-overlay" onClick={() => setShowImportCSV(false)}>
                    <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Import Contacts</h2>
                            <button
                                className="close-btn"
                                onClick={() => setShowImportCSV(false)}
                            >
                                ×
                            </button>
                        </div>
                        <form onSubmit={(e) => e.preventDefault()} className="form">
                            <div className="form-group">
                                <label>Import File *</label>
                                <input
                                    type="file"
                                    accept=".csv,.xlsx,.xls,.txt"
                                    onChange={handleFileSelect}
                                    required
                                />
                                <small>
                                    Supported: CSV, Excel (.xlsx, .xls), TXT (one email per line).
                                    All valid email domains are accepted.
                                </small>
                            </div>

                            <div className="form-group">
                                <label>Contact List (Optional)</label>
                                <select
                                    value={csvListId || ''}
                                    onChange={(e) => setCsvListId(e.target.value ? Number(e.target.value) : null)}
                                >
                                    <option value="">No list</option>
                                    {contactLists.map((list) => (
                                        <option key={list.id} value={list.id}>{list.name}</option>
                                    ))}
                                </select>
                                <small>If selected, imported contacts will be added to this list</small>
                            </div>

                            <div className="form-group">
                                <button
                                    type="button"
                                    className="btn-secondary"
                                    style={{ width: '100%' }}
                                    onClick={handleDownloadTemplate}
                                >
                                    📥 Download CSV Template
                                </button>
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
                            {validationReport && !showValidationReport && (
                                <div className="validation-preview-summary">
                                    <span className="validation-preview-valid">
                                        {validationReport.validEmails} valid
                                    </span>
                                    {validationReport.errors.length > 0 && (
                                        <span className="validation-preview-invalid">
                                            {validationReport.errors.length} invalid
                                        </span>
                                    )}
                                    <button
                                        type="button"
                                        className="btn-ghost"
                                        onClick={() => setShowValidationReport(true)}
                                    >
                                        View validation report
                                    </button>
                                </div>
                            )}
                            <div className="modal-actions">
                                <button
                                    type="button"
                                    className="btn-primary"
                                    disabled={!csvFile || !validationReport || validationReport.validEmails === 0 || importProgress !== ''}
                                    onClick={() => {
                                        if (validationReport && validationReport.validEmails > 0) {
                                            setShowValidationReport(true);
                                        }
                                    }}
                                >
                                    {validationReport
                                        ? `Preview & Import (${validationReport.validEmails} valid)`
                                        : csvFile
                                          ? 'Validating...'
                                          : 'Select File First'}
                                </button>
                                <button
                                    type="button"
                                    className="btn-secondary"
                                    onClick={() => {
                                        setShowImportCSV(false);
                                        setValidationReport(null);
                                        setCsvFile(null);
                                    }}
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Validation Report Modal */}
            {showValidationReport && validationReport && (
                <ValidationReportComponent
                    report={validationReport}
                    onAutoFixSuggestions={handleAutoFixSuggestions}
                    onProceedWithImport={
                        validationReport.validEmails > 0 ? handleProceedWithImport : undefined
                    }
                    onClose={() => setShowValidationReport(false)}
                />
            )}

            {showCreateList && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h2>Create contact list</h2>
                        <form onSubmit={handleCreateList}>
                            <div className="form-group">
                                <label>List name</label>
                                <input
                                    required
                                    value={newListName}
                                    onChange={(e) => setNewListName(e.target.value)}
                                    placeholder="Newsletter subscribers"
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="submit" className="btn-primary">Create</button>
                                <button type="button" className="btn-secondary" onClick={() => setShowCreateList(false)}>
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

        </PageShell>
    );
};

export default ContactManagement;
