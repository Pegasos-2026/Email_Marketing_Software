import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function parseSSEChunk(buffer: string): { events: Array<{ event: string; data: unknown }>; rest: string } {
    const events: Array<{ event: string; data: unknown }> = [];
    const blocks = buffer.split('\n\n');
    const rest = blocks.pop() ?? '';

    for (const block of blocks) {
        if (!block.trim()) continue;
        let event = 'message';
        let dataLine = '';
        for (const line of block.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            if (line.startsWith('data:')) dataLine = line.slice(5).trim();
        }
        if (dataLine) {
            try {
                events.push({ event, data: JSON.parse(dataLine) });
            } catch {
                /* ignore malformed chunks */
            }
        }
    }
    return { events, rest };
}

export function useAnalyticsStream<T>(
    streamPath: string | null,
    pollFn: () => Promise<T>,
    deps: unknown[] = []
) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [live, setLive] = useState(false);
    const [error, setError] = useState('');
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const applyData = useCallback((payload: T) => {
        setData(payload);
        setLastUpdated(new Date());
        setError('');
        setLoading(false);
    }, []);

    const pollOnce = useCallback(async () => {
        try {
            const result = await pollFn();
            applyData(result);
        } catch (err: any) {
            setError(
                err.response?.data?.detail ||
                    err.response?.data?.error ||
                    err.message ||
                    'Failed to load analytics'
            );
            setLoading(false);
        }
    }, [pollFn, applyData]);

    useEffect(() => {
        let cancelled = false;
        let fallbackTimer: ReturnType<typeof setInterval> | null = null;

        const clearFallback = () => {
            if (fallbackTimer) {
                clearInterval(fallbackTimer);
                fallbackTimer = null;
            }
        };

        const startFallback = () => {
            setLive(false);
            clearFallback();
            pollOnce();
            fallbackTimer = setInterval(pollOnce, 5000);
        };

        const connectStream = async () => {
            pollOnce();

            if (!streamPath) {
                startFallback();
                return;
            }

            const token = localStorage.getItem('access_token');
            if (!token) {
                startFallback();
                return;
            }

            abortRef.current?.abort();
            const controller = new AbortController();
            abortRef.current = controller;

            try {
                const response = await fetch(`${API_BASE}${streamPath}`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        Accept: 'text/event-stream',
                    },
                    signal: controller.signal,
                });

                if (!response.ok || !response.body) {
                    throw new Error('Stream unavailable');
                }

                clearFallback();
                setLive(true);

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (!cancelled) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const { events, rest } = parseSSEChunk(buffer);
                    buffer = rest;
                    for (const evt of events) {
                        if (evt.event === 'analytics') {
                            applyData(evt.data as T);
                        }
                    }
                }

                if (!cancelled) startFallback();
            } catch (err: any) {
                if (err.name !== 'AbortError' && !cancelled) {
                    startFallback();
                }
            }
        };

        connectStream();

        return () => {
            cancelled = true;
            abortRef.current?.abort();
            clearFallback();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [streamPath, ...deps]);

    const refresh = useCallback(() => pollOnce(), [pollOnce]);

    return { data, loading, live, error, lastUpdated, refresh };
}
