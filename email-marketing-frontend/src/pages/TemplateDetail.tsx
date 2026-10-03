import React, { useEffect, useState } from 'react';
import { useHistory, useParams } from 'react-router-dom';
import { templateService } from '../services/templateService';
import PageShell from '../components/ui/PageShell';
import '../styles/templates.css';

const TemplateDetail: React.FC = () => {
    const { templateId } = useParams<{ templateId: string }>();
    const history = useHistory();
    const [template, setTemplate] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const loadTemplate = async () => {
            try {
                const fetched = await templateService.getTemplate(Number(templateId));
                setTemplate(fetched);
            } catch (err: any) {
                setError(err.response?.data?.detail || 'Failed to load template');
            } finally {
                setLoading(false);
            }
        };
        loadTemplate();
    }, [templateId]);

    const handleDelete = async () => {
        if (!window.confirm('Delete this template? This action cannot be undone.')) {
            return;
        }
        try {
            await templateService.deleteTemplate(Number(templateId));
            history.push('/templates');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Unable to delete template');
        }
    };

    if (loading) {
        return <div className="loading">Loading template details...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    if (!template) {
        return <div className="error-message">Template not found.</div>;
    }

    return (
        <PageShell
            title={template.name || 'Template detail'}
            subtitle={`Category: ${template.category || 'N/A'} | Status: ${template.is_active ? 'Active' : 'Inactive'}`}
            actions={
                <>
                    <button className="btn-primary" onClick={() => history.push(`/templates/${templateId}/edit`)}>
                        Edit
                    </button>
                    <button className="btn-secondary" onClick={() => history.push('/templates')}>
                        Back to templates
                    </button>
                    <button className="btn-danger" onClick={handleDelete}>
                        Delete
                    </button>
                </>
            }
        >
            <div className="template-detail-page">
                <section className="template-summary">
                    <div className="summary-row">
                        <strong>Subject</strong>
                        <span>{template.subject || '—'}</span>
                    </div>
                    <div className="summary-row">
                        <strong>Preview text</strong>
                        <span>{template.preview_text || '—'}</span>
                    </div>
                </section>

                <section className="template-content-block">
                    <h2>Rendered preview</h2>
                    {template.html_content ? (
                        <div className="preview-container">
                            <iframe
                                title="Template preview"
                                className="preview-frame"
                                sandbox="allow-same-origin allow-scripts"
                                srcDoc={template.html_content}
                            />
                        </div>
                    ) : (
                        <div className="template-content-preview">No HTML content available.</div>
                    )}
                </section>

                <section className="template-content-block">
                    <h2>HTML source</h2>
                    <pre className="template-content-preview">
                        {template.html_content || 'No HTML content available.'}
                    </pre>
                </section>

                <section className="template-content-block">
                    <h2>Plain text source</h2>
                    <pre className="template-content-preview">
                        {template.plain_text_content || 'No plain text content available.'}
                    </pre>
                </section>
            </div>
        </PageShell>
    );
};

export default TemplateDetail;
