import React from 'react';
import { Link } from 'react-router-dom';

interface EmptyStateProps {
    title: string;
    description?: string;
    actionLabel?: string;
    actionTo?: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({
    title,
    description,
    actionLabel,
    actionTo,
}) => (
    <div className="empty-state">
        <h3>{title}</h3>
        {description && <p>{description}</p>}
        {actionLabel && actionTo && (
            <Link to={actionTo} className="btn-primary">
                {actionLabel}
            </Link>
        )}
    </div>
);

export default EmptyState;
