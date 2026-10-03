import React, { useMemo } from 'react';

export interface DonutSegment {
    label: string;
    value: number;
    color: string;
}

interface DonutChartProps {
    segments: DonutSegment[];
}

const DonutChart: React.FC<DonutChartProps> = ({ segments }) => {
    const { gradient, total } = useMemo(() => {
        const sum = segments.reduce((a, s) => a + s.value, 0) || 1;
        let acc = 0;
        const stops = segments.map((s) => {
            const start = (acc / sum) * 100;
            acc += s.value;
            const end = (acc / sum) * 100;
            return `${s.color} ${start}% ${end}%`;
        });
        return {
            gradient: `conic-gradient(${stops.join(', ')})`,
            total: sum,
        };
    }, [segments]);

    if (total === 0) {
        return <p className="text-muted">No data yet</p>;
    }

    return (
        <div className="donut-chart">
            <div
                className="donut-ring"
                style={{
                    background: gradient,
                    mask: 'radial-gradient(circle, transparent 42%, black 43%)',
                    WebkitMask: 'radial-gradient(circle, transparent 42%, black 43%)',
                }}
            />
            <div className="donut-legend">
                {segments.map((s) => (
                    <div key={s.label} className="donut-legend-item">
                        <span
                            className="donut-legend-swatch"
                            style={{ background: s.color }}
                        />
                        <span>{s.label}</span>
                        <strong>{s.value}</strong>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default DonutChart;
