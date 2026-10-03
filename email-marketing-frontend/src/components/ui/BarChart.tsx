import React from 'react';

export interface BarChartItem {
    label: string;
    value: number;
    color?: string;
}

interface BarChartProps {
    data: BarChartItem[];
    maxValue?: number;
}

const BarChart: React.FC<BarChartProps> = ({ data, maxValue }) => {
    const max = maxValue ?? Math.max(...data.map((d) => d.value), 1);

    return (
        <div className="bar-chart" role="img" aria-label="Bar chart">
            {data.map((item) => {
                const pct = max > 0 ? (item.value / max) * 100 : 0;
                return (
                    <div key={item.label} className="bar-chart-item">
                        <div className="bar-chart-bar-wrap">
                            <div
                                className="bar-chart-bar"
                                style={{
                                    height: `${Math.max(pct, 2)}%`,
                                    background: item.color
                                        ? item.color
                                        : undefined,
                                }}
                                title={`${item.label}: ${item.value}`}
                            />
                        </div>
                        <span className="bar-chart-value">{item.value}</span>
                        <span className="bar-chart-label">{item.label}</span>
                    </div>
                );
            })}
        </div>
    );
};

export default BarChart;
