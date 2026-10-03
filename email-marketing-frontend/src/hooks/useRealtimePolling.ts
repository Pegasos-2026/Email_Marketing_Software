import { useCallback, useEffect, useRef, useState } from 'react';

const DEFAULT_INTERVAL_MS = 5000;

/**
 * Polls a fetch function on an interval. Initial load sets loading=true;
 * subsequent polls refresh silently unless showLoadingOnRefresh is true.
 */
export function useRealtimePolling<T>(
    fetchFn: () => Promise<T>,
    deps: unknown[] = [],
    intervalMs: number = DEFAULT_INTERVAL_MS
) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const isMounted = useRef(true);

    const load = useCallback(async (silent: boolean): Promise<void> => {
            if (!silent) {
                setLoading(true);
            } else {
                setRefreshing(true);
            }
            setError('');
            try {
                const result = await fetchFn();
                if (isMounted.current) {
                    setData(result);
                    setLastUpdated(new Date());
                }
            } catch (err: any) {
                if (isMounted.current) {
                    const message =
                        err.response?.data?.detail ||
                        err.response?.data?.error ||
                        err.message ||
                        'Failed to load data';
                    setError(message);
                }
            } finally {
                if (isMounted.current) {
                    setLoading(false);
                    setRefreshing(false);
                }
            }
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [fetchFn, ...deps]
    );

    useEffect(() => {
        isMounted.current = true;
        load(false);
        const interval = setInterval(() => load(true), intervalMs);
        return () => {
            isMounted.current = false;
            clearInterval(interval);
        };
    }, [load, intervalMs]);

    const refresh = useCallback(() => load(true), [load]);

    return { data, loading, refreshing, error, lastUpdated, refresh };
}
