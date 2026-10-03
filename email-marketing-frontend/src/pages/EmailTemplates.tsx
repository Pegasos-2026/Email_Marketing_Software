import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { templateService } from '../services/templateService';
import { getApiErrorMessage } from '../utils/apiError';
import { EmailTemplate } from '../types';
import PageShell from '../components/ui/PageShell';
import EmptyState from '../components/ui/EmptyState';
import '../styles/templates.css';

const EmailTemplates: React.FC = () => {
    const [templates, setTemplates] = useState<EmailTemplate[]>([]);
    const [categories, setCategories] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [filter, setFilter] = useState('all');

    useEffect(() => {
        templateService
            .getTemplates()
            .then(({ templates: templateData, categories: categoryMap }) => {
                setTemplates(templateData);
                setCategories(['all', ...Object.keys(categoryMap)]);
            })
            .catch((err: any) => {
                setError(getApiErrorMessage(err, 'Failed to load templates'));
            })
            .finally(() => setLoading(false));
    }, []);

    const filteredTemplates =
        filter === 'all' ? templates : templates.filter((t) => t.category === filter);

    const handleDelete = async (id: number) => {
        if (!window.confirm('Delete this template?')) return;
        try {
            await templateService.deleteTemplate(id);
            setTemplates(templates.filter((t) => t.id !== id));
        } catch (err: any) {
            alert(getApiErrorMessage(err, 'Failed to delete template'));
        }
    };

    if (loading) {
        return <div className="loading-spinner">Loading templates…</div>;
    }

    return (
        <PageShell
            title="Email templates"
            subtitle="Reusable designs for campaigns. Filter by category or create a new template."
            actions={
                <Link to="/templates/create" className="btn-primary">
                    New template
                </Link>
            }
        >
            {error && <div className="alert alert-error">{error}</div>}

            <div className="filter-tabs">
                {categories.map((cat) => (
                    <button
                        key={cat}
                        type="button"
                        className={`filter-tab ${filter === cat ? 'active' : ''}`}
                        onClick={() => setFilter(cat)}
                    >
                        {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
                    </button>
                ))}
            </div>

            {filteredTemplates.length > 0 ? (
                <div className="templates-grid">
                    {filteredTemplates.map((template) => (
                        <article key={template.id} className="template-card">
                            <h3>{template.name}</h3>
                            <p className="template-category">{template.category}</p>
                            <p className="template-subject">Subject: {template.subject}</p>
                            <p className="template-date">
                                Created {new Date(template.created_at).toLocaleDateString()}
                            </p>
                            <div className="card-actions">
                                <Link
                                    to={`/templates/${template.id}`}
                                    className="btn-secondary btn-small"
                                >
                                    View
                                </Link>
                                <Link
                                    to={`/templates/${template.id}/edit`}
                                    className="btn-secondary btn-small"
                                >
                                    Edit
                                </Link>
                                <button
                                    type="button"
                                    onClick={() => handleDelete(template.id)}
                                    className="btn-small btn-delete"
                                >
                                    Delete
                                </button>
                            </div>
                        </article>
                    ))}
                </div>
            ) : (
                <EmptyState
                    title="No templates"
                    description="Create a template to speed up campaign creation."
                    actionLabel="Create template"
                    actionTo="/templates/create"
                />
            )}
        </PageShell>
    );
};

export default EmailTemplates;
