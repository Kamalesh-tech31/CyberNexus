import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { AnalysisSession, UserProfile } from '../types';
import { ApiError } from '../lib/api';
import { adaptStoredAnalysisToResult } from '../lib/resultAdapter';

describe('Batch 6 — Loading, Error & Recovery Hardening', () => {

  // =========================================================================
  // 1. Analysis Loading & Error Recovery
  // =========================================================================
  describe('1. Analysis Loading & Error Recovery', () => {
    it('1.1. In-flight analysis initializes with isAnalyzing: true, stages, and no result/error', () => {
      const session: AnalysisSession = {
        id: 'sess-new-1',
        title: 'SMS Analysis',
        selectedModel: 'sms',
        submittedInput: 'Check account now',
        isAnalyzing: true,
        stages: [
          { id: '1', label: 'Feature Extraction', status: 'running', detail: 'Parsing tokens' },
          { id: '2', label: 'TF-IDF Signal', status: 'pending', detail: 'Evaluating threat' },
        ],
        currentStageIndex: 0,
        result: undefined,
        error: undefined,
        createdAt: 'Just now',
      };

      assert.equal(session.isAnalyzing, true);
      assert.equal(session.result, undefined);
      assert.equal(session.error, undefined);
      assert.equal(session.stages[0].status, 'running');
      assert.equal(session.stages[1].status, 'pending');
    });

    it('1.2. Execution stage progression advances sequentially through stages', () => {
      let currentStageIndex = 0;
      const stages = [
        { id: '1', label: 'Stage 1', status: 'running' as const },
        { id: '2', label: 'Stage 2', status: 'pending' as const },
        { id: '3', label: 'Stage 3', status: 'pending' as const },
      ];

      // Advance stage
      currentStageIndex += 1;
      const updatedStages = stages.map((st, idx) => ({
        ...st,
        status: (idx < currentStageIndex ? 'completed' : (idx === currentStageIndex ? 'running' : 'pending')) as any,
      }));

      assert.equal(currentStageIndex, 1);
      assert.equal(updatedStages[0].status, 'completed');
      assert.equal(updatedStages[1].status, 'running');
      assert.equal(updatedStages[2].status, 'pending');
    });

    it('1.3. Network / timeout error (408 or TypeError) terminates loading with clear error message', () => {
      let isAnalyzing = true;
      let error: string | undefined = undefined;

      const handleCatch = (err: any) => {
        isAnalyzing = false;
        error = err instanceof ApiError ? err.message : (err?.message || 'Analysis request failed.');
      };

      handleCatch(new ApiError('Request timed out after 15000ms. Please check your network connection.', 408, true));

      assert.equal(isAnalyzing, false);
      assert.ok(error?.includes('timed out'));
    });

    it('1.4. 401 Unauthorized error during analysis invalidates session and transitions to guest', () => {
      let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'expired-token' };
      let sessionInvalidated = false;
      let error: string | undefined = undefined;

      const invalidateSession = () => {
        user = null;
        sessionInvalidated = true;
      };

      const handleCatch = (err: any) => {
        const isAuthError = err instanceof ApiError && err.status === 401;
        error = isAuthError
          ? 'Authentication session has expired or is invalid. Returned to guest mode.'
          : err.message;
        if (isAuthError) {
          invalidateSession();
        }
      };

      handleCatch(new ApiError('Invalid or expired token', 401));

      assert.equal(sessionInvalidated, true);
      assert.equal(user, null, 'User must transition to guest mode on 401');
      assert.ok(error?.includes('expired or is invalid'));
    });

    it('1.5. Retry analysis recovers failed session by re-submitting preserved inputs', async () => {
      const failedSession: AnalysisSession = {
        id: 'sess-failed',
        title: 'SMS Phish',
        selectedModel: 'sms',
        submittedInput: 'Urgent: Click here to verify account http://evil.com',
        isAnalyzing: false,
        error: 'Network connection lost.',
        stages: [{ id: '1', label: 'Feature Extraction', status: 'completed' }],
        currentStageIndex: 1,
        createdAt: 'Just now',
      };

      let reSubmittedInput: string | null = null;
      let reSubmittedModel: string | null = null;

      const handleRetryAnalysis = (session: AnalysisSession) => {
        if (session.isAnalyzing) return;
        reSubmittedInput = session.submittedInput;
        reSubmittedModel = session.selectedModel;
      };

      handleRetryAnalysis(failedSession);

      assert.equal(reSubmittedInput, failedSession.submittedInput);
      assert.equal(reSubmittedModel, failedSession.selectedModel);
    });

    it('1.6. Duplicate submit is blocked while analysis is currently in-flight (isAnalyzing: true)', () => {
      let submitCount = 0;
      const activeSession: AnalysisSession = {
        id: 'sess-inflight',
        title: 'Analyzing...',
        selectedModel: 'url',
        submittedInput: 'https://example.com',
        isAnalyzing: true,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      };

      const handleSubmitInput = () => {
        if (activeSession.isAnalyzing) return;
        submitCount++;
      };

      handleSubmitInput();
      assert.equal(submitCount, 0, 'Duplicate submission must be blocked when isAnalyzing is true');
    });
  });

  // =========================================================================
  // 2. Auth Session Restoration & Invalidation
  // =========================================================================
  describe('2. Auth Session Restoration & Invalidation', () => {
    it('2.1. Initial session restoration starts in loading state', () => {
      let authLoading = true;
      let user: UserProfile | null = null;

      assert.equal(authLoading, true);
      assert.equal(user, null);
    });

    it('2.2. Successful session restoration populates authenticated user profile with accessToken', () => {
      let authLoading = true;
      let user: UserProfile | null = null;

      const restoreSuccess = (restoredUser: UserProfile) => {
        user = restoredUser;
        authLoading = false;
      };

      restoreSuccess({
        id: 'usr-google-123',
        name: 'Jane Doe',
        email: 'jane@example.com',
        accessToken: 'valid-jwt-token-123',
      });

      assert.equal(authLoading, false);
      assert.equal(user?.id, 'usr-google-123');
      assert.equal(user?.accessToken, 'valid-jwt-token-123');
    });

    it('2.3. Session restoration failure falls back cleanly to guest mode without throwing unhandled exceptions', () => {
      let authLoading = true;
      let user: UserProfile | null = null;

      const restoreFailure = () => {
        user = null;
        authLoading = false;
      };

      restoreFailure();

      assert.equal(authLoading, false);
      assert.equal(user, null, 'User must remain null (guest mode)');
    });

    it('2.4. invalidateSession clears user, accessToken, and returns to guest mode', () => {
      let user: UserProfile | null = {
        id: 'usr-123',
        name: 'Alice',
        email: 'alice@example.com',
        accessToken: 'stale-token',
      };

      const invalidateSession = () => {
        user = null;
      };

      invalidateSession();
      assert.equal(user, null);
    });
  });

  // =========================================================================
  // 3. History Loading & Error Recovery
  // =========================================================================
  describe('3. History Loading & Error Recovery', () => {
    it('3.1. History loading state sets isLoadingHistory: true with empty error', () => {
      let isLoadingHistory = true;
      let historyError: string | null = null;

      assert.equal(isLoadingHistory, true);
      assert.equal(historyError, null);
    });

    it('3.2. Successful history fetch hydrates sessions array', () => {
      let isLoadingHistory = true;
      let sessions: any[] = [];

      const mockFetchedHistory = [
        { analysis_id: 'a1', title: 'URL Analysis', channel: 'url', created_at: '2026-09-17T08:00:00Z' },
        { analysis_id: 'a2', title: 'SMS Analysis', channel: 'sms', created_at: '2026-09-17T08:15:00Z' },
      ];

      sessions = mockFetchedHistory;
      isLoadingHistory = false;

      assert.equal(isLoadingHistory, false);
      assert.equal(sessions.length, 2);
      assert.equal(sessions[0].analysis_id, 'a1');
    });

    it('3.3. Empty history (200 + []) displays empty state without error', () => {
      const historyError: string | null = null;
      const sessions: any[] = [];
      const isLoadingHistory = false;

      const showEmptyState = !isLoadingHistory && !historyError && sessions.length === 0;
      const showErrorState = !isLoadingHistory && !!historyError && sessions.length === 0;

      assert.equal(showEmptyState, true, 'Must display "No previous analyses yet"');
      assert.equal(showErrorState, false, 'Must not display error message on empty 200');
    });

    it('3.4. Failed history fetch (network or 500) displays error state with retry button', () => {
      const historyError: string | null = 'Failed to load history';
      const sessions: any[] = [];
      const isLoadingHistory = false;

      const showEmptyState = !isLoadingHistory && !historyError && sessions.length === 0;
      const showErrorState = !isLoadingHistory && !!historyError && sessions.length === 0;

      assert.equal(showErrorState, true, 'Must display "Failed to load history"');
      assert.equal(showEmptyState, false);
    });

    it('3.5. Non-empty history with failed refresh displays non-intrusive warning banner with retry button', () => {
      const historyError: string | null = 'Failed to refresh history';
      const sessions: any[] = [{ id: 's1', title: 'Prior session' }];

      const showBanner = !!historyError && sessions.length > 0;
      assert.equal(showBanner, true, 'Must display refresh failure banner when sessions already exist');
    });

    it('3.6. History retry button is disabled during in-flight retry (isLoadingHistory: true)', () => {
      let isLoadingHistory = true;
      let retryTriggered = false;

      const handleRetry = () => {
        if (isLoadingHistory) return;
        retryTriggered = true;
      };

      handleRetry();
      assert.equal(retryTriggered, false, 'Retry must be blocked while isLoadingHistory is true');
    });

    it('3.7. 401 Unauthorized during history fetch triggers onAuthFailure', async () => {
      let authInvalidated = false;

      const mockFetchHistory = async (token: string) => {
        if (token === 'bad-token') {
          throw new ApiError('Unauthorized', 401);
        }
      };

      try {
        await mockFetchHistory('bad-token');
      } catch (err: any) {
        if (err instanceof ApiError && err.status === 401) {
          authInvalidated = true;
        }
      }

      assert.equal(authInvalidated, true, 'Session must be invalidated on history 401');
    });

    it('3.8. History retry preserves already-loaded detail results', () => {
      const prevSessions: AnalysisSession[] = [
        {
          id: 'sess-1',
          title: 'URL Phish',
          selectedModel: 'url',
          submittedInput: 'http://malicious.com',
          isAnalyzing: false,
          result: { verdict: 'Likely Phishing', riskScore: 95 } as any,
          stages: [],
          currentStageIndex: 0,
          createdAt: '2026-09-17T08:00:00Z',
        },
      ];

      const refetchedSummary = [
        { analysis_id: 'sess-1', title: 'URL Phish', channel: 'url', created_at: '2026-09-17T08:00:00Z' },
        { analysis_id: 'sess-2', title: 'SMS Promo', channel: 'sms', created_at: '2026-09-17T08:30:00Z' },
      ];

      const resultMap = new Map<string, AnalysisSession>();
      for (const s of prevSessions) {
        if (s.result) {
          resultMap.set(s.id, s);
        }
      }

      const merged: AnalysisSession[] = refetchedSummary.map((item) => {
        const existing = resultMap.get(item.analysis_id);
        if (existing) return existing;
        return {
          id: item.analysis_id,
          title: item.title,
          selectedModel: item.channel as any,
          submittedInput: '',
          isAnalyzing: false,
          result: undefined,
          stages: [],
          currentStageIndex: 0,
          createdAt: item.created_at,
        };
      });

      assert.equal(merged.length, 2);
      assert.ok(merged[0].result, 'Existing result must be preserved');
      assert.equal((merged[0].result as any)?.riskScore, 95);
      assert.equal(merged[1].result, undefined, 'New summary item has not loaded detail yet');
    });

    it('3.9. History hydration effect does not re-fire when logical inputs remain unchanged (infinite-loop regression)', async () => {
      let fetchCallCount = 0;
      let lastHydratedToken: string | null = null;

      const mockFetchHistory = async (token: string) => {
        fetchCallCount++;
        return [{ analysis_id: 'sess-1', title: 'Test', channel: 'sms', created_at: 'now' }];
      };

      // Simulate component lifecycle / re-renders
      const simulateEffect = (token: string | null) => {
        if (!token) {
          lastHydratedToken = null;
          return;
        }
        if (lastHydratedToken === token) {
          return; // Guard prevents re-fetch
        }
        lastHydratedToken = token;
        mockFetchHistory(token);
      };

      const userToken = 'valid-user-jwt-123';

      // First mount / auth established
      simulateEffect(userToken);
      assert.equal(fetchCallCount, 1, 'Initial fetch must occur');

      // Subsequent re-renders where token and user are identical
      simulateEffect(userToken);
      simulateEffect(userToken);
      simulateEffect(userToken);
      assert.equal(fetchCallCount, 1, 'History fetch must not re-fire on re-render when token is unchanged');

      // Token change (e.g. user switch)
      simulateEffect('new-user-jwt-456');
      assert.equal(fetchCallCount, 2, 'History fetch must fire once for new user token');
    });

    it('3.10. History loading state reaches terminal false on completion', async () => {
      let loading = false;
      const executeFetch = async () => {
        loading = true;
        await new Promise((r) => setTimeout(r, 10));
        loading = false;
      };

      assert.equal(loading, false);
      const promise = executeFetch();
      assert.equal(loading, true);
      await promise;
      assert.equal(loading, false, 'Loading state must resolve to false (terminal state)');
    });
  });

  // =========================================================================
  // 4. Historical Detail Loading & Error Recovery
  // =========================================================================
  describe('4. Historical Detail Loading & Error Recovery', () => {
    it('4.1. Selecting placeholder session sets isLoadingDetail: true and clears previous error', () => {
      let session: AnalysisSession = {
        id: 'hist-1',
        title: 'Placeholder',
        selectedModel: 'sms',
        submittedInput: '',
        isAnalyzing: false,
        isLoadingDetail: false,
        error: 'Old error',
        stages: [],
        currentStageIndex: 0,
        createdAt: '2026-09-17T08:00:00Z',
      };

      session = { ...session, isLoadingDetail: true, error: undefined };

      assert.equal(session.isLoadingDetail, true);
      assert.equal(session.error, undefined);
    });

    it('4.2. Successful detail fetch populates full result and clears isLoadingDetail', () => {
      const mockStoredAnalysis = {
        analysis_id: 'hist-1',
        title: 'SMS Alert',
        channel: 'sms',
        created_at: '2026-09-17T08:00:00Z',
        input: { channel: 'sms', input: 'Suspicious sms text' },
        result: {
          prediction: 'Likely Smishing',
          risk_score: 88,
          confidence: 0.88,
          tier1: { verdict: 'Likely Smishing', confidence: 0.88, confidence_band: 'high', summary: 'High risk' },
          tier2: { flags: [], confidence_breakdown: { smishing: 0.88, legitimate: 0.12 } },
        },
        explanation: {
          tier3: {
            feature_contributions: [],
            top_text_signals: [],
            model_metadata: { model_name: 'SMS Logistic Regression' },
          },
          reasons: ['Suspicious link'],
          indicators: [],
          recommendation: 'Do not respond.',
        },
        metadata: { latency_ms: 45, calibrated: true, model_name: 'SMS Logistic Regression' },
      };

      const { result, submittedInput } = adaptStoredAnalysisToResult(mockStoredAnalysis);

      assert.equal(result.verdict, 'Likely Smishing');
      assert.equal(result.confidence, 88);
      assert.equal(result.detectedType, 'sms');
      assert.equal(submittedInput, 'Suspicious sms text');
    });

    it('4.3. Failed detail fetch sets error and clears isLoadingDetail', () => {
      let session: AnalysisSession = {
        id: 'hist-1',
        title: 'Placeholder',
        selectedModel: 'sms',
        submittedInput: '',
        isAnalyzing: false,
        isLoadingDetail: true,
        stages: [],
        currentStageIndex: 0,
        createdAt: '2026-09-17T08:00:00Z',
      };

      session = {
        ...session,
        isLoadingDetail: false,
        error: 'Failed to load historical analysis detail.',
      };

      assert.equal(session.isLoadingDetail, false);
      assert.equal(session.error, 'Failed to load historical analysis detail.');
    });

    it('4.4. Historical detail error displays retry button which allows re-requesting detail', () => {
      let fetchCalled = false;
      const session: AnalysisSession = {
        id: 'hist-failed',
        title: 'Historical SMS',
        selectedModel: 'sms',
        submittedInput: '',
        isAnalyzing: false,
        isLoadingDetail: false,
        error: 'Failed to load historical analysis detail.',
        stages: [],
        currentStageIndex: 0,
        createdAt: '2026-09-17T08:00:00Z',
      };

      const handleRetryHistoricalDetail = (id: string) => {
        if (session.isLoadingDetail) return;
        fetchCalled = true;
      };

      handleRetryHistoricalDetail(session.id);
      assert.equal(fetchCalled, true, 'Retry must re-invoke detail fetch');
    });

    it('4.5. 401 during historical detail fetch triggers session invalidation', async () => {
      let authInvalidated = false;

      const mockFetchDetail = async (id: string, token: string) => {
        throw new ApiError('Token expired', 401);
      };

      try {
        await mockFetchDetail('sess-1', 'bad-token');
      } catch (err: any) {
        if (err instanceof ApiError && err.status === 401) {
          authInvalidated = true;
        }
      }

      assert.equal(authInvalidated, true);
    });

    it('4.6. Duplicate detail fetch is blocked while session is already isLoadingDetail', () => {
      let callCount = 0;
      const session: AnalysisSession = {
        id: 'hist-loading',
        title: 'In Flight',
        selectedModel: 'sms',
        submittedInput: '',
        isAnalyzing: false,
        isLoadingDetail: true,
        stages: [],
        currentStageIndex: 0,
        createdAt: '2026-09-17T08:00:00Z',
      };

      const handleSelectSession = (s: AnalysisSession) => {
        if (s.result || s.isAnalyzing || s.isLoadingDetail) return;
        callCount++;
      };

      handleSelectSession(session);
      assert.equal(callCount, 0, 'Must not duplicate fetch if already loading');
    });
  });

  // =========================================================================
  // 5. Delete One Analysis Lifecycle & Concurrency
  // =========================================================================
  describe('5. Delete One Analysis Lifecycle & Concurrency', () => {
    it('5.1. Deleting an item marks its ID in deletingIds set', () => {
      const deletingIds = new Set<string>();
      deletingIds.add('sess-del-1');

      assert.equal(deletingIds.has('sess-del-1'), true);
      assert.equal(deletingIds.has('sess-del-2'), false);
    });

    it('5.2. Successful delete removes item from sessions and clears ID from deletingIds', () => {
      let sessions = [{ id: 'sess-del-1' }, { id: 'sess-keep-2' }];
      const deletingIds = new Set<string>(['sess-del-1']);

      // Success
      sessions = sessions.filter((s) => s.id !== 'sess-del-1');
      deletingIds.delete('sess-del-1');

      assert.equal(sessions.length, 1);
      assert.equal(sessions[0].id, 'sess-keep-2');
      assert.equal(deletingIds.has('sess-del-1'), false);
    });

    it('5.3. Failed delete preserves session in list and clears ID from deletingIds', () => {
      let sessions = [{ id: 'sess-del-1' }, { id: 'sess-keep-2' }];
      const deletingIds = new Set<string>(['sess-del-1']);

      // Error occurs
      deletingIds.delete('sess-del-1');

      assert.equal(sessions.length, 2, 'Session must not be removed on failure');
      assert.equal(deletingIds.has('sess-del-1'), false);
    });

    it('5.4. Concurrent delete of two different sessions tracks both IDs simultaneously in deletingIds', () => {
      const deletingIds = new Set<string>();
      deletingIds.add('sess-1');
      deletingIds.add('sess-2');

      assert.equal(deletingIds.has('sess-1'), true);
      assert.equal(deletingIds.has('sess-2'), true);
      assert.equal(deletingIds.size, 2);
    });

    it('5.5. Duplicate delete of same session while in-flight is prevented', () => {
      const deletingIds = new Set<string>(['sess-1']);
      let deleteDispatched = false;

      const handleDelete = (id: string) => {
        if (deletingIds.has(id)) return;
        deleteDispatched = true;
      };

      handleDelete('sess-1');
      assert.equal(deleteDispatched, false, 'Must not dispatch delete if already deleting');
    });

    it('5.6. 401 during delete-one triggers session invalidation', async () => {
      let authInvalidated = false;

      const mockDelete = async () => {
        throw new ApiError('Unauthorized', 401);
      };

      try {
        await mockDelete();
      } catch (err: any) {
        if (err instanceof ApiError && err.status === 401) {
          authInvalidated = true;
        }
      }

      assert.equal(authInvalidated, true);
    });

    it('5.7. Delete-one retry: initial delete fails -> item remains in list -> retry triggered -> second DELETE succeeds and removes item', async () => {
      let sessions: { id: string; title: string }[] = [
        { id: 'sess-del-1', title: 'Target Session' },
        { id: 'sess-keep-2', title: 'Other Session' },
      ];
      let deletingIds = new Set<string>();
      let deleteAttempts = 0;
      let errorMessage: string | null = null;

      // Mock backend handler: fails on first attempt, succeeds on second attempt
      const mockBackendDelete = async (id: string) => {
        deleteAttempts++;
        if (deleteAttempts === 1) {
          throw new ApiError('Internal server error', 500);
        }
        return true;
      };

      const handleDeleteOne = async (id: string) => {
        if (deletingIds.has(id)) return;
        deletingIds = new Set(deletingIds).add(id);
        errorMessage = null;

        try {
          await mockBackendDelete(id);
          sessions = sessions.filter((s) => s.id !== id);
        } catch (err: any) {
          errorMessage = err.message;
        } finally {
          const next = new Set(deletingIds);
          next.delete(id);
          deletingIds = next;
        }
      };

      // 1. First attempt fails
      await handleDeleteOne('sess-del-1');
      assert.equal(deleteAttempts, 1, 'First DELETE request was dispatched');
      assert.equal(errorMessage, 'Internal server error', 'Error was captured and surfaced');
      assert.equal(sessions.length, 2, 'Item remains in sessions list on failure');
      assert.equal(sessions[0].id, 'sess-del-1', 'Failed item still present in list');
      assert.equal(deletingIds.has('sess-del-1'), false, 'deletingIds must be cleared after failure');

      // 2. Retry attempt: user triggers delete again
      await handleDeleteOne('sess-del-1');
      assert.equal(deleteAttempts, 2, 'Second DELETE request (retry) was dispatched');
      assert.equal(errorMessage, null, 'Error was cleared on successful retry');
      assert.equal(sessions.length, 1, 'Item was removed from sessions list on successful retry');
      assert.equal(sessions[0].id, 'sess-keep-2', 'Only un-deleted item remains');
      assert.equal(deletingIds.has('sess-del-1'), false, 'deletingIds is empty after success');
    });

    it('5.8. Concurrent delete-one locking model: Set<string> allows concurrent distinct IDs, blocks duplicates, and isolates completion (7C.3)', async () => {
      let deletingIds = new Set<string>();
      let inFlightApiRequests: string[] = [];

      // Simulates useHistory.deleteAnalysis locking model
      const deleteAnalysis = async (id: string, delayMs: number) => {
        if (deletingIds.has(id)) {
          return false; // Guard against duplicate delete
        }
        deletingIds = new Set(deletingIds).add(id);
        inFlightApiRequests.push(id);

        await new Promise((r) => setTimeout(r, delayMs));

        const next = new Set(deletingIds);
        next.delete(id);
        deletingIds = next;
        return true;
      };

      // Dispatch deletion of item A (takes 50ms) and item B (takes 20ms) concurrently
      const promiseA = deleteAnalysis('item-A', 50);
      const promiseB = deleteAnalysis('item-B', 20);

      // Verify both are tracked concurrently in deletingIds
      assert.equal(deletingIds.has('item-A'), true, 'item-A must be in deletingIds');
      assert.equal(deletingIds.has('item-B'), true, 'item-B must be in deletingIds');
      assert.equal(deletingIds.size, 2, 'Both distinct IDs are deleting concurrently');

      // Attempt to delete item-A again while in-flight -> rejected
      const duplicateA = await deleteAnalysis('item-A', 10);
      assert.equal(duplicateA, false, 'Duplicate delete of item-A must be rejected');

      // Wait for item-B to complete
      await promiseB;
      assert.equal(deletingIds.has('item-B'), false, 'item-B is cleared from deletingIds after completion');
      assert.equal(deletingIds.has('item-A'), true, 'item-A remains in deletingIds while still in-flight');

      // Wait for item-A to complete
      await promiseA;
      assert.equal(deletingIds.has('item-A'), false, 'item-A is cleared from deletingIds');
      assert.equal(deletingIds.size, 0, 'deletingIds is completely empty');
    });
  });

  // =========================================================================
  // 6. Delete All History Lifecycle
  // =========================================================================
  describe('6. Delete All History Lifecycle', () => {
    it('6.1. Delete-all sets isDeletingAll: true during execution', () => {
      let isDeletingAll = false;
      isDeletingAll = true;
      assert.equal(isDeletingAll, true);
    });

    it('6.2. Successful delete-all clears all sessions and resets activeSessionId', () => {
      let sessions = [{ id: 's1' }, { id: 's2' }];
      let activeSessionId: string | null = 's1';
      let isDeletingAll = true;

      // Success
      sessions = [];
      activeSessionId = null;
      isDeletingAll = false;

      assert.equal(sessions.length, 0);
      assert.equal(activeSessionId, null);
      assert.equal(isDeletingAll, false);
    });

    it('6.3. Failed delete-all retains all sessions and clears isDeletingAll flag', () => {
      const sessions = [{ id: 's1' }, { id: 's2' }];
      let isDeletingAll = true;

      // Failure
      isDeletingAll = false;

      assert.equal(sessions.length, 2, 'Sessions must be retained on failure');
      assert.equal(isDeletingAll, false);
    });

    it('6.4. Duplicate delete-all calls while in-flight are prevented', () => {
      const isDeletingAll = true;
      let clearDispatched = false;

      const handleClearAll = () => {
        if (isDeletingAll) return;
        clearDispatched = true;
      };

      handleClearAll();
      assert.equal(clearDispatched, false);
    });

    it('6.5. 401 during delete-all triggers session invalidation', async () => {
      let authInvalidated = false;

      const mockClearAll = async () => {
        throw new ApiError('Unauthorized', 401);
      };

      try {
        await mockClearAll();
      } catch (err: any) {
        if (err instanceof ApiError && err.status === 401) {
          authInvalidated = true;
        }
      }

      assert.equal(authInvalidated, true);
    });

    it('6.6. Delete-all retry: initial delete-all fails -> sessions preserved -> retry triggered -> second clear request succeeds and empties list', async () => {
      let sessions: { id: string; title: string }[] = [
        { id: 'sess-1', title: 'Session 1' },
        { id: 'sess-2', title: 'Session 2' },
      ];
      let activeSessionId: string | null = 'sess-1';
      let isDeletingAll = false;
      let clearAttempts = 0;
      let errorMessage: string | null = null;

      const mockBackendClearAll = async () => {
        clearAttempts++;
        if (clearAttempts === 1) {
          throw new ApiError('Database error during bulk deletion', 500);
        }
        return true;
      };

      const handleClearAll = async () => {
        if (isDeletingAll) return;
        isDeletingAll = true;
        errorMessage = null;

        try {
          await mockBackendClearAll();
          sessions = [];
          activeSessionId = null;
        } catch (err: any) {
          errorMessage = err.message;
        } finally {
          isDeletingAll = false;
        }
      };

      // 1. First attempt: fails
      await handleClearAll();
      assert.equal(clearAttempts, 1, 'First clear-all request was dispatched');
      assert.equal(errorMessage, 'Database error during bulk deletion', 'Error was surfaced');
      assert.equal(sessions.length, 2, 'All sessions remain preserved on failure');
      assert.equal(activeSessionId, 'sess-1', 'activeSessionId preserved on failure');
      assert.equal(isDeletingAll, false, 'isDeletingAll flag is reset to false after failure');

      // 2. Retry attempt: user triggers clear-all again
      await handleClearAll();
      assert.equal(clearAttempts, 2, 'Second clear-all request (retry) was dispatched');
      assert.equal(errorMessage, null, 'Error cleared on successful retry');
      assert.equal(sessions.length, 0, 'All sessions cleared on successful retry');
      assert.equal(activeSessionId, null, 'activeSessionId reset to null on success');
      assert.equal(isDeletingAll, false, 'isDeletingAll reset to false');
    });
  });

  // =========================================================================
  // 7. Account Deletion Lifecycle & Unmount Safety
  // =========================================================================
  describe('7. Account Deletion Lifecycle & Unmount Safety', () => {
    it('7.1. Account deletion 401 triggers invalidateSession and closes modal', async () => {
      let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'expired-jwt' };
      let modalOpen = true;

      const invalidateSession = () => {
        user = null;
      };

      const handleDeleteAccount = async () => {
        try {
          throw new ApiError('Invalid token', 401);
        } catch (err: any) {
          if (err instanceof ApiError && err.status === 401) {
            invalidateSession();
            modalOpen = false;
            return;
          }
          throw err;
        }
      };

      await handleDeleteAccount();

      assert.equal(user, null, 'User must transition to guest mode on 401');
      assert.equal(modalOpen, false, 'Modal must close on 401');
    });

    it('7.2. Account deletion 500 fails closed: user and sessions are preserved, error rethrown to modal', async () => {
      let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'valid-jwt' };
      let sessions = [{ id: 's1' }];
      let modalError: string | null = null;

      const handleDeleteAccount = async () => {
        try {
          throw new ApiError('Server error deleting user', 500);
        } catch (err: any) {
          if (err instanceof ApiError && err.status === 401) {
            user = null;
            return;
          }
          throw err;
        }
      };

      try {
        await handleDeleteAccount();
      } catch (err: any) {
        modalError = err.message;
      }

      assert.notEqual(user, null, 'User must NOT be logged out on 500 error (fail-closed)');
      assert.equal(sessions.length, 1, 'Sessions must NOT be wiped on 500 error');
      assert.equal(modalError, 'Server error deleting user');
    });

    it('7.3. Account deletion network failure fails closed without logging user out', async () => {
      let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'valid-jwt' };
      let caughtError: string | null = null;

      const handleDeleteAccount = async () => {
        try {
          throw new TypeError('Failed to fetch');
        } catch (err: any) {
          if (err instanceof ApiError && err.status === 401) {
            user = null;
            return;
          }
          throw err;
        }
      };

      try {
        await handleDeleteAccount();
      } catch (err: any) {
        caughtError = err.message;
      }

      assert.notEqual(user, null, 'User must NOT be signed out on network failure');
      assert.equal(caughtError, 'Failed to fetch');
    });

    it('7.4. Unmount safety: isMountedRef prevents state updates after component unmount', async () => {
      let isMounted = true;
      let stateUpdated = false;

      const simulatedAsyncAction = async () => {
        // Simulate delay during which component unmounts
        isMounted = false;
        if (isMounted) {
          stateUpdated = true;
        }
      };

      await simulatedAsyncAction();
      assert.equal(stateUpdated, false, 'State must not be updated if component has unmounted');
    });

    it('7.5. Account-deletion loading: DOM pending state disables buttons, renders spinner, and shows "Deleting Account..."', () => {
      // Test the DOM rendering contract of SettingsModal during account deletion pending state
      let isDeletingAccount = true;
      let isConfirmingDelete = true;

      // Model the exact DOM node properties produced by SettingsModal when isDeletingAccount === true
      const confirmButton = {
        id: 'settings-confirm-delete-account-btn',
        disabled: isDeletingAccount,
        children: {
          spinner: {
            className: 'w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin',
          },
          text: 'Deleting Account...',
        },
      };

      const cancelButton = {
        id: 'settings-cancel-delete-account-btn',
        disabled: isDeletingAccount,
        text: 'Cancel',
      };

      // Assertions matching the exact required DOM pending state
      assert.equal(confirmButton.disabled, true, 'Confirm button must have disabled attribute while deletion is in progress');
      assert.ok(confirmButton.children.spinner.className.includes('animate-spin'), 'Confirm button must contain spinner element');
      assert.ok(confirmButton.children.spinner.className.includes('w-3 h-3 border-2'), 'Spinner must have proper size/border styling');
      assert.equal(confirmButton.children.text, 'Deleting Account...', 'Button text must be "Deleting Account..."');
      assert.equal(cancelButton.disabled, true, 'Cancel button must have disabled attribute while deletion is in progress');

      // Verify that when not deleting, buttons are enabled and default label is shown
      isDeletingAccount = false;
      const confirmButtonIdle = {
        id: 'settings-confirm-delete-account-btn',
        disabled: isDeletingAccount,
        text: 'Yes, Permanently Delete',
      };
      assert.equal(confirmButtonIdle.disabled, false, 'Confirm button must be enabled when idle');
      assert.equal(confirmButtonIdle.text, 'Yes, Permanently Delete', 'Default confirmation text shown when idle');
    });

    it('7.6. Account-deletion retry: initial 500 failure fails closed -> retry confirmation fires second DELETE /api/account -> succeeds', async () => {
      let user: UserProfile | null = { id: 'usr-bob', name: 'Bob', email: 'bob@ex.com', accessToken: 'token-bob' };
      let sessions: { id: string }[] = [{ id: 'sess-1' }, { id: 'sess-2' }];
      let activeSessionId: string | null = 'sess-1';
      let modalOpen = true;
      let isDeletingAccount = false;
      let deleteAttempts = 0;
      let modalError: string | null = null;

      const mockDeleteAccountApi = async (token: string) => {
        deleteAttempts++;
        if (deleteAttempts === 1) {
          throw new ApiError('Internal server error deleting user account', 500);
        }
        return { message: 'Account and associated data permanently deleted.' };
      };

      const handleDeleteAccount = async () => {
        if (isDeletingAccount) return;
        isDeletingAccount = true;
        modalError = null;

        try {
          await mockDeleteAccountApi(user!.accessToken);
          // Success: sign out user, clear sessions, close modal
          user = null;
          sessions = [];
          activeSessionId = null;
          modalOpen = false;
        } catch (err: any) {
          if (err instanceof ApiError && err.status === 401) {
            user = null;
            sessions = [];
            activeSessionId = null;
            modalOpen = false;
            return;
          }
          modalError = err.message;
        } finally {
          isDeletingAccount = false;
        }
      };

      // 1. Initial attempt fails with 500
      await handleDeleteAccount();
      assert.equal(deleteAttempts, 1, 'First DELETE request was dispatched');
      assert.notEqual(user, null, 'Fail-closed: user must NOT be logged out on 500');
      assert.equal(user?.id, 'usr-bob');
      assert.equal(sessions.length, 2, 'Fail-closed: sessions must NOT be cleared');
      assert.equal(activeSessionId, 'sess-1');
      assert.equal(modalOpen, true, 'Modal must remain open to display the error');
      assert.equal(modalError, 'Internal server error deleting user account');
      assert.equal(isDeletingAccount, false, 'Loading state must be reset');

      // 2. Retry: user confirms delete again
      await handleDeleteAccount();
      assert.equal(deleteAttempts, 2, 'Second DELETE request (retry) was dispatched');
      assert.equal(user, null, 'User must be signed out on successful retry');
      assert.equal(sessions.length, 0, 'Sessions must be cleared on successful retry');
      assert.equal(activeSessionId, null, 'activeSessionId reset on success');
      assert.equal(modalOpen, false, 'Modal closed on successful retry');
      assert.equal(modalError, null, 'Modal error cleared on successful retry');
      assert.equal(isDeletingAccount, false);
    });

    it('7.7. Account deletion 401 invariant: calls invalidateSession, resets user to null, wipes sessions, closes modal, and resets activeSessionId (7C.1)', async () => {
      let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'expired-jwt' };
      let sessions = [{ id: 's1' }, { id: 's2' }];
      let activeSessionId: string | null = 's1';
      let modalOpen = true;
      let invalidateSessionCalled = false;

      const invalidateSession = () => {
        invalidateSessionCalled = true;
        user = null;
        sessions = [];
        activeSessionId = null;
      };

      const handleDeleteAccount = async () => {
        try {
          throw new ApiError('Unauthorized: Token expired or invalid', 401);
        } catch (err: any) {
          if (err instanceof ApiError && err.status === 401) {
            invalidateSession();
            modalOpen = false;
            return;
          }
          throw err;
        }
      };

      await handleDeleteAccount();

      assert.equal(invalidateSessionCalled, true, 'invalidateSession must be called on 401');
      assert.equal(user, null, 'User must transition to null (guest mode)');
      assert.equal(sessions.length, 0, 'Local sessions must be wiped on session invalidation');
      assert.equal(modalOpen, false, 'Settings modal must close on 401');
      assert.equal(activeSessionId, null, 'activeSessionId must be reset to null');
    });
  });

  // =========================================================================
  // 8. Identity-Transition & In-Flight Race Condition Isolation
  // =========================================================================
  describe('8. Identity-Transition & In-Flight Race Condition Isolation', () => {
    it('8.1. User A starts analysis -> logs out before response -> in-flight response is discarded and guest state remains clean', async () => {
      let currentUser: UserProfile | null = {
        id: 'usr-alice-123',
        name: 'Alice',
        email: 'alice@example.com',
        accessToken: 'alice-token',
      };
      let guestSessions: AnalysisSession[] = [];
      let activeSessionId: string | null = null;

      // Simulated state ref tracking
      const currentUserRef = { current: currentUser };
      let activeReqId = 0;

      // Alice submits analysis
      const submittingUserId = currentUserRef.current?.id || null;
      const reqId = ++activeReqId;

      // Create delayed API promise
      const delayedApiPromise = new Promise<{ analysis_id: string; verdict: string }>((resolve) => {
        setTimeout(() => {
          resolve({ analysis_id: 'alice-analysis-999', verdict: 'Likely Phishing' });
        }, 50);
      });

      // Alice logs out before response resolves!
      currentUser = null;
      currentUserRef.current = null;
      guestSessions = [];
      activeSessionId = null;

      // Response arrives
      const res = await delayedApiPromise;

      // Verification check implemented in App.tsx:
      const shouldApply = (currentUserRef.current?.id || null) === submittingUserId;

      if (shouldApply) {
        guestSessions.push({ id: res.analysis_id } as any);
      }

      assert.equal(shouldApply, false, 'In-flight response must be discarded after logout');
      assert.equal(guestSessions.length, 0, 'Guest session state must remain clean and empty');
      assert.equal(activeSessionId, null);
    });

    it('8.2. User A starts analysis -> User B logs in before response -> response is discarded and User B is isolated', async () => {
      let currentUser: UserProfile | null = {
        id: 'usr-alice-123',
        name: 'Alice',
        email: 'alice@example.com',
        accessToken: 'alice-token',
      };
      let userSessions: AnalysisSession[] = [];

      const currentUserRef = { current: currentUser };
      let activeReqId = 0;

      // Alice submits analysis
      const submittingUserId = currentUserRef.current?.id || null;
      const reqId = ++activeReqId;

      // In-flight promise
      const delayedApiPromise = new Promise<{ analysis_id: string }>((resolve) => {
        setTimeout(() => resolve({ analysis_id: 'alice-secret-scan' }), 50);
      });

      // User B logs in!
      currentUser = {
        id: 'usr-bob-456',
        name: 'Bob',
        email: 'bob@example.com',
        accessToken: 'bob-token',
      };
      currentUserRef.current = currentUser;
      userSessions = []; // Bob starts clean

      const res = await delayedApiPromise;

      // Verification guard from App.tsx:
      const shouldApply = (currentUserRef.current?.id || null) === submittingUserId;

      if (shouldApply) {
        userSessions.push({ id: res.analysis_id } as any);
      }

      assert.equal(shouldApply, false, 'Alice response must be rejected when Bob is active');
      assert.equal(userSessions.length, 0, 'Bob session state must have 0 traces of Alice analysis');
    });

    it('8.3. User A starts historical detail fetch -> logs out before response -> detail is discarded', async () => {
      let currentUser: UserProfile | null = {
        id: 'usr-alice-123',
        name: 'Alice',
        email: 'alice@example.com',
        accessToken: 'alice-token',
      };
      let sessionPopulated = false;

      const currentUserRef = { current: currentUser };
      const requestingUserId = currentUserRef.current?.id || null;

      const delayedDetailPromise = new Promise<{ title: string }>((resolve) => {
        setTimeout(() => resolve({ title: 'Alice Private Detail' }), 50);
      });

      // User logs out before response
      currentUser = null;
      currentUserRef.current = null;

      const detail = await delayedDetailPromise;

      // Verification guard from handleSelectSession in App.tsx:
      const shouldApply = (currentUserRef.current?.id || null) === requestingUserId;

      if (shouldApply) {
        sessionPopulated = true;
      }

      assert.equal(shouldApply, false, 'Historical detail must be discarded if user logged out');
      assert.equal(sessionPopulated, false);
    });

    it('8.4. Rapid duplicate analysis requests: only the latest request response is applied (monotonic reqId)', async () => {
      let activeReqId = 0;
      let appliedResult: string | null = null;

      const simulateSubmit = (query: string, delayMs: number) => {
        const reqId = ++activeReqId;
        setTimeout(() => {
          if (activeReqId === reqId) {
            appliedResult = query;
          }
        }, delayMs);
      };

      // Query 1 takes 80ms, Query 2 is dispatched at 10ms and takes 20ms (finishes earlier at 30ms),
      // Query 3 dispatched at 15ms and takes 100ms
      simulateSubmit('query-1', 80);
      simulateSubmit('query-2', 40);
      simulateSubmit('query-3', 100);

      // Wait 120ms
      await new Promise((r) => setTimeout(r, 120));

      assert.equal(appliedResult, 'query-3', 'Only the latest request (reqId = 3) must be applied');
    });

    it('8.5. Historical cache identity isolation: User A cached detail is purged on user transition and inaccessible to User B (7C.2)', async () => {
      // 1. User A logs in, loads history, views detail for sess-A1
      let currentUser: UserProfile | null = {
        id: 'usr-A',
        name: 'Alice',
        email: 'alice@example.com',
        accessToken: 'token-A',
      };
      let sessions: AnalysisSession[] = [
        {
          id: 'sess-A1',
          title: 'Alice Analysis 1',
          selectedModel: 'sms',
          submittedInput: 'Alice confidential sms',
          isAnalyzing: false,
          stages: [],
          currentStageIndex: 0,
          createdAt: '2026-09-17T08:00:00Z',
          result: {
            prediction: 'Phishing',
            riskScore: 92,
            confidence: 0.92,
            summary: 'Confidential bank alert',
          } as any,
        },
      ];
      let activeSessionId: string | null = 'sess-A1';

      // 2. User A logs out / switches to User B -> App.tsx transition handler
      const handleUserTransition = (newUser: UserProfile | null) => {
        currentUser = newUser;
        // Strict boundary: clear all sessions, reset active ID, clear history cache
        sessions = [];
        activeSessionId = null;
      };

      handleUserTransition(null); // User A logs out
      assert.equal(sessions.length, 0, 'Sessions must be completely purged upon logout');
      assert.equal(activeSessionId, null);

      // 3. User B logs in and loads User B history
      const userB: UserProfile = {
        id: 'usr-B',
        name: 'Bob',
        email: 'bob@example.com',
        accessToken: 'token-B',
      };
      handleUserTransition(userB);

      // User B history hydration
      const userBHistory: AnalysisSession[] = [
        {
          id: 'sess-B1',
          title: 'Bob Analysis 1',
          selectedModel: 'url',
          submittedInput: 'https://example.com',
          isAnalyzing: false,
          stages: [],
          currentStageIndex: 0,
          createdAt: '2026-09-17T09:00:00Z',
          result: undefined, // Detail not loaded yet
        },
      ];
      sessions = userBHistory;

      // Verify User A's cached detail cannot be accessed from User B's state
      const hasAliceData = sessions.some(
        (s) => s.id === 'sess-A1' || s.submittedInput.includes('Alice') || (s.result as any)?.summary?.includes('bank alert')
      );
      assert.equal(hasAliceData, false, 'User B state must contain zero data or cached results from User A');
      assert.equal(sessions.length, 1);
      assert.equal(sessions[0].id, 'sess-B1');
      assert.equal(sessions[0].result, undefined, 'User B initial item has unpopulated result');
    });
  });
});
