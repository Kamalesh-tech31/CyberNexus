import { useState, useCallback, useRef, useEffect } from 'react';
import { 
  fetchUserHistory, 
  fetchUserAnalysis, 
  deleteUserAnalysis, 
  deleteAllUserHistory, 
  HistoryItemApiResponse, 
  ApiError 
} from '../lib/api';
import { AnalysisSession, AnalysisType } from '../types';

export interface UseHistoryOptions {
  onAuthFailure?: () => void;
}

export interface HistoryHook {
  history: HistoryItemApiResponse[];
  loading: boolean;
  error: string | null;
  deletingIds: Set<string>;
  isDeletingAll: boolean;
  fetchHistory: (accessToken: string) => Promise<HistoryItemApiResponse[] | null>;
  fetchAnalysisDetail: (analysisId: string, accessToken: string) => Promise<any | null>;
  deleteAnalysis: (analysisId: string, accessToken: string) => Promise<boolean>;
  clearAllUserHistory: (accessToken: string) => Promise<boolean>;
  refreshHistory: (accessToken: string) => Promise<void>;
  clearHistory: () => void;
  addHistoryItem: (item: HistoryItemApiResponse) => void;
}

/**
 * Transforms a backend HistoryItemApiResponse into an AnalysisSession representation
 * strictly preserving backend-confirmed identity (analysis_id, created_at).
 */
export function mapHistoryItemToSession(item: HistoryItemApiResponse): AnalysisSession {
  const channel = (item.channel.toLowerCase() as AnalysisType) || 'auto';
  return {
    id: item.analysis_id,
    title: item.title || `${item.channel.toUpperCase()} Analysis`,
    selectedModel: channel,
    submittedInput: '',
    isAnalyzing: false,
    stages: [],
    currentStageIndex: 0,
    createdAt: item.created_at,
  };
}

/**
 * Custom hook managing authenticated persistent analysis history.
 * Bound to verified Supabase access tokens; guest users remain tokenless and ephemeral.
 */
export function useHistory(options?: UseHistoryOptions): HistoryHook {
  const [history, setHistory] = useState<HistoryItemApiResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [isDeletingAll, setIsDeletingAll] = useState<boolean>(false);

  // Monotonically increasing request ID to prevent race conditions and stale responses
  const activeRequestIdRef = useRef<number>(0);
  const activeDetailIdRef = useRef<number>(0);
  const isMountedRef = useRef<boolean>(true);

  // Store options in a ref so callbacks don't recreate when options object identity changes
  const optionsRef = useRef<UseHistoryOptions | undefined>(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  const deletingIdsRef = useRef<Set<string>>(deletingIds);
  useEffect(() => {
    deletingIdsRef.current = deletingIds;
  }, [deletingIds]);

  const isDeletingAllRef = useRef<boolean>(isDeletingAll);
  useEffect(() => {
    isDeletingAllRef.current = isDeletingAll;
  }, [isDeletingAll]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      activeRequestIdRef.current++;
      activeDetailIdRef.current++;
    };
  }, []);

  const fetchHistory = useCallback(
    async (accessToken: string): Promise<HistoryItemApiResponse[] | null> => {
      if (!accessToken) {
        setHistory([]);
        setLoading(false);
        setError(null);
        return null;
      }

      const requestId = ++activeRequestIdRef.current;
      setLoading(true);
      setError(null);

      try {
        const data = await fetchUserHistory(accessToken);

        // Discard if unmounted, a newer request was dispatched, or identity cleared
        if (!isMountedRef.current || requestId !== activeRequestIdRef.current) {
          return null;
        }

        setHistory(data);
        return data;
      } catch (err: any) {
        if (!isMountedRef.current || requestId !== activeRequestIdRef.current) {
          return null;
        }

        const is401 = err instanceof ApiError && err.status === 401;
        if (is401) {
          optionsRef.current?.onAuthFailure?.();
          setError('Authentication session expired.');
        } else {
          setError(err?.message || 'Failed to retrieve analysis history.');
        }
        return null;
      } finally {
        if (isMountedRef.current && requestId === activeRequestIdRef.current) {
          setLoading(false);
        }
      }
    },
    []
  );

  const fetchAnalysisDetail = useCallback(
    async (analysisId: string, accessToken: string): Promise<any | null> => {
      if (!analysisId || !accessToken) {
        return null;
      }

      const detailId = ++activeDetailIdRef.current;

      try {
        const data = await fetchUserAnalysis(analysisId, accessToken);

        // Discard if unmounted, a newer request was dispatched, or session cleared
        if (!isMountedRef.current || detailId !== activeDetailIdRef.current) {
          return null;
        }

        return data;
      } catch (err: any) {
        if (!isMountedRef.current || detailId !== activeDetailIdRef.current) {
          return null;
        }

        const is401 = err instanceof ApiError && err.status === 401;
        if (is401) {
          optionsRef.current?.onAuthFailure?.();
          setError('Authentication session expired.');
        } else {
          setError(err?.message || 'Failed to retrieve analysis detail.');
        }
        return null;
      }
    },
    []
  );

  const deleteAnalysis = useCallback(
    async (analysisId: string, accessToken: string): Promise<boolean> => {
      if (!analysisId || !accessToken) return false;
      if (deletingIdsRef.current.has(analysisId)) return false; // Guard against double-click

      setDeletingIds((prev) => new Set(prev).add(analysisId));
      try {
        await deleteUserAnalysis(analysisId, accessToken);
        if (!isMountedRef.current) return false;

        // Remove from local history state upon backend success
        setHistory((prev) => prev.filter((item) => item.analysis_id !== analysisId));
        return true;
      } catch (err: any) {
        if (!isMountedRef.current) return false;
        const is401 = err instanceof ApiError && err.status === 401;
        if (is401) {
          optionsRef.current?.onAuthFailure?.();
          setError('Authentication session expired.');
        } else {
          setError(err?.message || 'Failed to delete analysis record.');
        }
        return false;
      } finally {
        if (isMountedRef.current) {
          setDeletingIds((prev) => {
            const next = new Set(prev);
            next.delete(analysisId);
            return next;
          });
        }
      }
    },
    []
  );

  const clearAllUserHistory = useCallback(
    async (accessToken: string): Promise<boolean> => {
      if (!accessToken || isDeletingAllRef.current) return false;

      setIsDeletingAll(true);
      try {
        await deleteAllUserHistory(accessToken);
        if (!isMountedRef.current) return false;

        // Clear local history upon backend confirmation
        setHistory([]);
        return true;
      } catch (err: any) {
        if (!isMountedRef.current) return false;
        const is401 = err instanceof ApiError && err.status === 401;
        if (is401) {
          optionsRef.current?.onAuthFailure?.();
          setError('Authentication session expired.');
        } else {
          setError(err?.message || 'Failed to clear analysis history.');
        }
        return false;
      } finally {
        if (isMountedRef.current) {
          setIsDeletingAll(false);
        }
      }
    },
    []
  );

  const refreshHistory = useCallback(
    async (accessToken: string) => {
      await fetchHistory(accessToken);
    },
    [fetchHistory]
  );

  const clearHistory = useCallback(() => {
    // Invalidate any in-flight requests immediately
    activeRequestIdRef.current++;
    activeDetailIdRef.current++;
    setHistory([]);
    setDeletingIds(new Set());
    setIsDeletingAll(false);
    setLoading(false);
    setError(null);
  }, []);

  const addHistoryItem = useCallback((item: HistoryItemApiResponse) => {
    setHistory((prev) => {
      // Prepend the new backend-confirmed history item (prevent duplicates)
      const filtered = prev.filter((h) => h.analysis_id !== item.analysis_id);
      return [item, ...filtered];
    });
  }, []);

  return {
    history,
    loading,
    error,
    deletingIds,
    isDeletingAll,
    fetchHistory,
    fetchAnalysisDetail,
    deleteAnalysis,
    clearAllUserHistory,
    refreshHistory,
    clearHistory,
    addHistoryItem,
  };
}
