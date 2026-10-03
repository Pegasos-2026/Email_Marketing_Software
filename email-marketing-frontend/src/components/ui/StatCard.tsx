import React from 'react';

interface StatCardProps {
    label: string;
    value: string | number;
    hint?: string;
    tone?: 'default' | 'success' | 'warning' | 'danger' | 'brand';
    icon?: string;
}

const StatCard: React.FC<StatCardProps> = ({
    label,
    value,
    hint,
    tone = 'default',
    icon,
}) => (
    <div className={`stat-card-ui stat-card-ui--${tone}`}>
        {icon && <span className="stat-card-ui-icon" aria-hidden>{icon}</span>}
        <div className="stat-card-ui-body">
            <span className="stat-card-ui-label">{label}</span>
            <span className="stat-card-ui-value">{value}</span>
            {hint != null && hint !== '' && (
                <span className="stat-card-ui-hint">{hint}</span>
            )}
        </div>
    </div>
);

export default StatCard;
