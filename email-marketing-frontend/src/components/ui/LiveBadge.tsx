import React from 'react';

const LiveBadge: React.FC<{ live: boolean }> = ({ live }) => (
    <span className={`live-badge ${live ? 'live-badge--on' : 'live-badge--off'}`}>
        <span className="live-badge-dot" aria-hidden />
        {live ? 'Live' : 'Polling'}
    </span>
);

export default LiveBadge;
