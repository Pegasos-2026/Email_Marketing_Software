import React, { useEffect, useState } from 'react';
import { dripService } from '../services/dripService';
import { Link } from 'react-router-dom';
import '../styles/drip.css';

const DripDashboard: React.FC = () => {
    const [campaigns, setCampaigns] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchCampaigns();
    }, []);

    const fetchCampaigns = async () => {
        setLoading(true);
        try {
            const data = await dripService.getDripCampaigns();
            setCampaigns(data || []);
        } catch (err) {
            console.error('Failed to load drip campaigns', err);
        } finally {
            setLoading(false);
        }
    };

    const handleActivate = async (campaignId: number) => {
        try {
            await dripService.activate(campaignId);
            await fetchCampaigns();
        } catch (err: any) {
            alert(err?.response?.data?.error || 'Failed to activate campaign');
        }
    };

    const summary = {
        total: campaigns.length,
        active: campaigns.filter((c) => c.status === 'active').length,
        paused: campaigns.filter((c) => c.status === 'paused').length,
        draft: campaigns.filter((c) => c.status === 'draft').length,
    };

    return (
        <div className="drip-dashboard">
            <div className="drip-header">
                <h1>Drip Campaigns</h1>
                <div>
                    <Link to="/drip/create" className="btn-primary">Create Drip Campaign</Link>
                </div>
            </div>

            <div className="drip-summary">
                <div className="summary-card">
                    <div className="summary-label">Total</div>
                    <strong>{summary.total}</strong>
                </div>
                <div className="summary-card">
                    <div className="summary-label">Active</div>
                    <strong>{summary.active}</strong>
                </div>
                <div className="summary-card">
                    <div className="summary-label">Paused</div>
                    <strong>{summary.paused}</strong>
                </div>
                <div className="summary-card">
                    <div className="summary-label">Drafts</div>
                    <strong>{summary.draft}</strong>
                </div>
            </div>

            <div className="drip-list">
                {loading ? (
                    <p>Loading…</p>
                ) : campaigns.length === 0 ? (
                    <p>No drip campaigns yet. Create one to get started.</p>
                ) : (
                    campaigns.map((c) => (
                        <div key={c.id} className="drip-card">
                            <div className="drip-card-header">
                                <h3>{c.name}</h3>
                                <div className="drip-actions">
                                    <Link to={`/drip/${c.id}`} className="btn-secondary">View</Link>
                                    <Link to={`/drip/${c.id}/builder`} className="btn-primary">Builder</Link>
                                    {(c.status === 'draft' || c.status === 'paused') && (c.total_steps ?? 0) > 0 && (
                                        <button
                                            type="button"
                                            className="btn-secondary"
                                            onClick={() => handleActivate(c.id)}
                                        >
                                            Activate
                                        </button>
                                    )}
                                </div>
                            </div>
                            <div className="drip-meta">
                                <div>Status: <strong>{c.status}</strong></div>
                                <div>Trigger: <strong>{c.trigger_type?.replace(/_/g, ' ')}</strong></div>
                                <div>Steps: <strong>{c.total_steps ?? 0}</strong></div>
                                <div>Enrolled: <strong>{c.total_enrollments ?? 0}</strong></div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default DripDashboard;
