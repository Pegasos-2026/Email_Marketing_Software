import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { campaignService } from '../services/campaignService';
import { getApiErrorMessage } from '../utils/apiError';
import { Campaign } from '../types';
import PageShell from './ui/PageShell';
import '../styles/campaigns.css';

const CampaignList: React.FC = () => {
    const [allCampaigns, setAllCampaigns] = useState<Campaign[]>([]);
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [filter, setFilter] = useState('all');

    useEffect(() => {
        const fetchCampaigns = async () => {
            try {
                const data = await campaignService.getCampaigns();
                setAllCampaigns(data);

                if (filter !== 'all') {
                    setCampaigns(data.filter((c: Campaign) => c.status === filter));
                } else {
                    setCampaigns(data);
                }
            } catch (err: any) {
                setError(getApiErrorMessage(err, 'Failed to load campaigns'));
            } finally {
                setLoading(false);
            }
        };
        fetchCampaigns();
    }, [filter]);

    const campaignCounts = allCampaigns.reduce(
        (acc, c) => ({
            all: acc.all + 1,
            draft: acc.draft + (c.status === 'draft' ? 1 : 0),
            sent: acc.sent + (c.status === 'sent' ? 1 : 0),
            scheduled: acc.scheduled + (c.status === 'scheduled' ? 1 : 0),
            sending: acc.sending + (c.status === 'sending' ? 1 : 0)
        }),
        { all: 0, draft: 0, sent: 0, scheduled: 0, sending: 0 }
    );

    const handleDelete = async (id: number) => {
        if (window.confirm('Are you sure you want to delete this campaign?')) {
            try {
                await campaignService.deleteCampaign(id);
                setCampaigns(campaigns.filter(c => c.id !== id));
                setAllCampaigns(allCampaigns.filter((c) => c.id !== id));
            } catch (err: any) {
                alert(getApiErrorMessage(err, 'Failed to delete campaign'));
            }
        }
    };

    if (loading) {
        return <div className="loading-spinner">Loading campaigns…</div>;
    }

    return (
        <PageShell
            title="Campaigns"
            subtitle="Create, schedule, and track email campaigns."
            actions={
                <Link to="/campaigns/create" className="btn-primary">
                    New campaign
                </Link>
            }
        >
            {error && <div className="alert alert-error">{error}</div>}

            <section className="campaigns-panel">
                <div className="campaign-summary">
                    <div className="summary-card">
                        <span className="summary-label">Total campaigns</span>
                        <strong>{campaignCounts.all}</strong>
                    </div>
                    <div className="summary-card">
                        <span className="summary-label">Draft campaigns</span>
                        <strong>{campaignCounts.draft}</strong>
                    </div>
                    <div className="summary-card">
                        <span className="summary-label">Scheduled campaigns</span>
                        <strong>{campaignCounts.scheduled}</strong>
                    </div>
                    <div className="summary-card">
                        <span className="summary-label">Currently sending</span>
                        <strong>{campaignCounts.sending}</strong>
                    </div>
                    <div className="summary-card">
                        <span className="summary-label">Sent campaigns</span>
                        <strong>{campaignCounts.sent}</strong>
                    </div>
                </div>

                <div className="filter-tabs">
                    {['all', 'draft', 'sent', 'scheduled', 'sending'].map((status) => (
                        <button
                            key={status}
                            className={`filter-tab ${filter === status ? 'active' : ''}`}
                            onClick={() => setFilter(status)}
                        >
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </button>
                    ))}
                </div>
            </section>

            {campaigns.length > 0 ? (
                <div className="campaigns-grid">
                    {campaigns.map((campaign) => (
                        <div key={campaign.id} className="campaign-card">
                            <div className="campaign-card-header">
                                <div>
                                    <h3>{campaign.name}</h3>
                                    <p className="campaign-subject">{campaign.subject}</p>
                                </div>
                                <span className={`status-badge status-${campaign.status}`}>
                                    {campaign.status}
                                </span>
                            </div>
                            <div className="campaign-card-meta">
                                <span>Created: {new Date(campaign.created_at).toLocaleDateString()}</span>
                                {campaign.status === 'scheduled' && campaign.scheduled_at && (
                                    <span className="scheduled-time">
                                        📅 Scheduled: {new Date(campaign.scheduled_at).toLocaleString()}
                                    </span>
                                )}
                                {campaign.status === 'sent' && campaign.sent_at && (
                                    <span>Sent: {new Date(campaign.sent_at).toLocaleDateString()}</span>
                                )}
                            </div>
                            <div className="campaign-card-actions">
                                <Link to={`/campaigns/${campaign.id}`} className="btn-secondary btn-small">
                                    View
                                </Link>
                                {campaign.status === 'draft' && (
                                    <>
                                        <Link to={`/campaigns/${campaign.id}/edit`} className="btn-secondary btn-small">
                                            Edit
                                        </Link>
                                        <button
                                            onClick={() => handleDelete(campaign.id)}
                                            className="btn-small btn-delete"
                                        >
                                            Delete
                                        </button>
                                    </>
                                )}
                                {campaign.status === 'sent' && (
                                    <Link to={`/campaigns/${campaign.id}/analytics`} className="btn-secondary btn-small">
                                        Analytics
                                    </Link>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="no-data">
                    <p>No campaigns found.</p>
                    <Link to="/campaigns/create" className="btn-primary">
                        Create your first campaign
                    </Link>
                </div>
            )}
        </PageShell>
    );
};

export default CampaignList;