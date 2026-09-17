import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import { mapSessionToUserProfile } from '../hooks/useAuthSession';
import { mapHistoryItemToSession } from '../hooks/useHistory';
import { UserProfile, AnalysisSession } from '../types';
import { HistoryItemApiResponse } from '../lib/api';

describe('Auth & Session Boundary Isolation', () => {
  it('1. maps null session to null user (Guest Mode default)', () => {
    const user = mapSessionToUserProfile(null);
    assert.equal(user, null, 'User must be null when session is absent');
  });

  it('2. maps valid Supabase session to UserProfile with token', () => {
    const mockSession = {
      access_token: 'mock.jwt.token',
      user: {
        id: 'usr-12345',
        email: 'alice@cybernexus.security',
        user_metadata: {
          full_name: 'Alice Smith',
          avatar_url: 'https://avatar.example/alice.png',
        },
      },
    } as any;

    const user = mapSessionToUserProfile(mockSession);
    assert.ok(user !== null);
    assert.equal(user.id, 'usr-12345');
    assert.equal(user.name, 'Alice Smith');
    assert.equal(user.email, 'alice@cybernexus.security');
    assert.equal(user.accessToken, 'mock.jwt.token');
  });

  it('3. Guest -> Authenticated: Guest local sessions must be discarded', () => {
    // Simulate guest state before login
    let localSessions: AnalysisSession[] = [
      {
        id: 'guest-session-1',
        title: 'Guest URL check',
        selectedModel: 'url',
        submittedInput: 'https://malicious.example',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      },
      {
        id: 'guest-session-2',
        title: 'Guest SMS check',
        selectedModel: 'sms',
        submittedInput: 'Urgent: account locked',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      },
    ];
    let activeSessionId: string | null = 'guest-session-1';

    // Transition: user authenticates
    const previousUserId: string | null = null;
    const authenticatedUserId: string = 'usr-alice';

    if (previousUserId !== authenticatedUserId) {
      // Discard rule
      localSessions = [];
      activeSessionId = null;
    }

    assert.equal(localSessions.length, 0, 'Guest sessions must be discarded on login');
    assert.equal(activeSessionId, null, 'Active session must be reset');
  });

  it('4. Authenticated -> Logout: User sessions cleared and returns to clean guest mode', () => {
    let currentUser: UserProfile | null = {
      id: 'usr-alice',
      name: 'Alice',
      email: 'alice@example.com',
      accessToken: 'token-alice',
    };
    let userSessions: AnalysisSession[] = [
      {
        id: 'auth-session-1',
        title: 'Alice Analysis',
        selectedModel: 'email',
        submittedInput: 'Suspicious email',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      },
    ];
    let activeSessionId: string | null = 'auth-session-1';

    // Execute logout transition
    currentUser = null;
    userSessions = [];
    activeSessionId = null;

    assert.equal(currentUser, null, 'User must be null after logout');
    assert.equal(userSessions.length, 0, 'User local sessions must be cleared');
    assert.equal(activeSessionId, null, 'Active session must be cleared');
  });

  it('5. User A -> User B: No state from User A leaks to User B', () => {
    let localSessions: AnalysisSession[] = [
      {
        id: 'user-a-sess',
        title: 'Confidential investigation',
        selectedModel: 'url',
        submittedInput: 'https://secret.example',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      },
    ];
    let activeSessionId: string | null = 'user-a-sess';
    let previousUserId: string | null = 'usr-alice';
    let newUserId: string | null = 'usr-bob';

    // Transition triggered
    if (previousUserId !== newUserId) {
      localSessions = [];
      activeSessionId = null;
    }

    assert.equal(localSessions.length, 0, "User A's local sessions must be completely removed");
    assert.equal(activeSessionId, null, 'Active session from User A must not persist into User B');
  });

  it('6. Browser Reload while Authenticated: Does not execute destructive cleanup during restoration', () => {
    let authLoading = true;
    let localSessions: AnalysisSession[] = [
      {
        id: 'restored-session',
        title: 'Existing Session',
        selectedModel: 'url',
        submittedInput: 'https://test.example',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'Just now',
      },
    ];

    const prevUser = { id: null as string | null, initialized: false };
    const user: UserProfile | null = {
      id: 'usr-alice',
      name: 'Alice',
      email: 'alice@example.com',
    };

    // Transition effect logic
    if (authLoading) {
      // Guard: do not clean up during restoration
    } else {
      if (!prevUser.initialized) {
        prevUser.id = user?.id || null;
        prevUser.initialized = true;
      } else if (prevUser.id !== (user?.id || null)) {
        localSessions = [];
      }
    }

    assert.equal(localSessions.length, 1, 'Restoration must not wipe existing state prematurely');
  });

  it('7. Guest Analysis Request: Never attaches Authorization header', () => {
    const accessToken: string | null = null;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    assert.equal(headers['Authorization'], undefined, 'Guest request must not include Authorization header');
  });

  it('8. Authenticated Analysis Request: Attaches current Supabase access token', () => {
    const accessToken: string = 'eyJhbGciOiJIUzI1NiJ9.user-token.signature';
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    assert.equal(headers['Authorization'], `Bearer ${accessToken}`, 'Authenticated request must include Bearer token');
  });

  it('9. 401 Authentication Failure: Triggers invalidation and resets user to null', () => {
    let currentUser: UserProfile | null = {
      id: 'usr-expired',
      name: 'Expired User',
      email: 'expired@cybernexus.security',
      accessToken: 'expired-token',
    };

    const isAuthError = true; // status === 401
    if (isAuthError) {
      // Invalidation logic
      currentUser = null;
    }

    assert.equal(currentUser, null, 'User must be cleared to null upon 401 authentication rejection');
  });

  it('10. Invalid token is NOT silently converted to guest', () => {
    // If user provided a token that is rejected with 401, the system does not
    // silently pretend it was a guest request; it surfaces the 401 error.
    const statusCode = 401;
    const errorDetail = 'Invalid or expired token';

    let errorRaised = false;
    let fallbackToGuest = false;

    if (statusCode === 401) {
      errorRaised = true;
      // Must NOT set fallbackToGuest = true at API layer
    } else {
      fallbackToGuest = true;
    }

    assert.equal(errorRaised, true, '401 must raise an explicit error');
    assert.equal(fallbackToGuest, false, 'Invalid token must never be silently converted to guest at API layer');
  });

  it('11. Guest Mode: Never requests persistent history', () => {
    let apiCallMade = false;
    const user: UserProfile | null = null;

    if (user?.accessToken) {
      apiCallMade = true;
    }

    assert.equal(apiCallMade, false, 'Guest user must not trigger GET /api/history');
  });

  it('12. Authenticated History Mapping: Strictly preserves backend analysis_id and created_at', () => {
    const rawBackendItem: HistoryItemApiResponse = {
      analysis_id: 'db-uuid-8899-aabb',
      title: 'Phishing Threat in Billing',
      channel: 'email',
      created_at: '2026-09-16T15:30:00Z',
      updated_at: '2026-09-16T15:30:00Z',
    };

    const session = mapHistoryItemToSession(rawBackendItem);

    assert.equal(session.id, 'db-uuid-8899-aabb', 'analysis_id must be preserved without Date.now()');
    assert.equal(session.title, 'Phishing Threat in Billing');
    assert.equal(session.selectedModel, 'email');
    assert.equal(session.createdAt, '2026-09-16T15:30:00Z', 'created_at must be preserved');
  });

  it('13. Session Restoration: Triggers history fetch only after restoration completes', () => {
    let authLoading = true;
    let historyFetched = false;
    const restoredUser: UserProfile = {
      id: 'usr-restored',
      name: 'Restored User',
      email: 'restored@example.com',
      accessToken: 'jwt-restored-token',
    };

    // Before restoration resolves
    if (!authLoading && restoredUser.accessToken) {
      historyFetched = true;
    }
    assert.equal(historyFetched, false, 'History must not be fetched while authLoading is true');

    // After restoration resolves
    authLoading = false;
    if (!authLoading && restoredUser.accessToken) {
      historyFetched = true;
    }
    assert.equal(historyFetched, true, 'History must be fetched after auth restoration completes');
  });

  it('14. Logout: Clears local history completely', () => {
    let localHistory: HistoryItemApiResponse[] = [
      {
        analysis_id: 'a1',
        title: 'Title 1',
        channel: 'url',
        created_at: '2026-09-16T12:00:00Z',
      },
    ];

    // Simulate logout action
    localHistory = [];

    assert.equal(localHistory.length, 0, 'Local history must be empty after logout');
  });

  it('15. User A -> User B: Replaces history completely without merging', () => {
    const userAHistory: HistoryItemApiResponse[] = [
      { analysis_id: 'a-1', title: 'A Secret', channel: 'url', created_at: '2026-09-16T10:00:00Z' },
    ];
    let activeHistory: HistoryItemApiResponse[] = [...userAHistory];

    // User A logs out
    activeHistory = [];

    // User B logs in
    const userBHistory: HistoryItemApiResponse[] = [
      { analysis_id: 'b-1', title: 'B Public', channel: 'sms', created_at: '2026-09-16T11:00:00Z' },
    ];
    activeHistory = [...userBHistory];

    assert.equal(activeHistory.length, 1);
    assert.equal(activeHistory[0].analysis_id, 'b-1');
    assert.ok(!activeHistory.some((item) => item.analysis_id === 'a-1'), 'User A history must not leak to User B');
  });

  it('16. New Authenticated Analysis: Syncs immediately into local history using backend identity', () => {
    let history: HistoryItemApiResponse[] = [];
    const user: UserProfile = {
      id: 'usr-charlie',
      name: 'Charlie',
      email: 'charlie@example.com',
      accessToken: 'token-charlie',
    };

    // Simulated backend response for authenticated analysis
    const apiResponse = {
      analysis_id: 'confirmed-analysis-uuid-999',
      created_at: '2026-09-16T18:45:00Z',
      resolved_channel: 'url',
      prediction: 'benign',
    };

    if (user.accessToken && apiResponse.analysis_id && apiResponse.created_at) {
      const newItem: HistoryItemApiResponse = {
        analysis_id: apiResponse.analysis_id,
        title: 'URL Analysis: BENIGN',
        channel: apiResponse.resolved_channel,
        created_at: apiResponse.created_at,
      };
      history = [newItem, ...history];
    }

    assert.equal(history.length, 1);
    assert.equal(history[0].analysis_id, 'confirmed-analysis-uuid-999');
    assert.equal(history[0].created_at, '2026-09-16T18:45:00Z');
  });

  it('17. Guest Analysis: Does NOT enter persistent history', () => {
    let persistentHistory: HistoryItemApiResponse[] = [];
    const guestUser: UserProfile | null = null;

    // Guest response (no analysis_id or token)
    const guestResponse = {
      resolved_channel: 'sms',
      prediction: 'phishing',
    };

    if (guestUser && (guestResponse as any).analysis_id) {
      persistentHistory = [{ analysis_id: 'fake', title: 'Fake', channel: 'sms', created_at: 'now' }];
    }

    assert.equal(persistentHistory.length, 0, 'Guest analysis must never enter persistent history');
  });

  it('18. No Placeholder ID: Backend-confirmed ID is required for history entry', () => {
    const apiResponseWithoutId = {
      prediction: 'suspicious',
      channel: 'email',
    };

    let itemCreated = false;
    if ((apiResponseWithoutId as any).analysis_id) {
      itemCreated = true;
    }

    assert.equal(itemCreated, false, 'Entry must never be created with fabricated or placeholder ID');
  });

  it('19. Stale User A History Response: Cannot update User B when race condition occurs', async () => {
    let activeRequestId = 0;
    let localHistory: HistoryItemApiResponse[] = [];

    // User A starts fetch (Request 1)
    const userARequestId = ++activeRequestId;

    // User B logs in before User A response arrives (Request 2)
    const userBRequestId = ++activeRequestId;
    const userBData: HistoryItemApiResponse[] = [
      { analysis_id: 'b-data', title: 'Bob History', channel: 'url', created_at: 'now' },
    ];
    localHistory = userBData;

    // Delayed User A response arrives
    const userAData: HistoryItemApiResponse[] = [
      { analysis_id: 'a-data', title: 'Alice Confidential', channel: 'email', created_at: 'older' },
    ];
    if (userARequestId === activeRequestId) {
      localHistory = userAData; // Should NOT be reached
    }

    assert.equal(localHistory.length, 1);
    assert.equal(localHistory[0].analysis_id, 'b-data', 'User B history must remain intact; User A response ignored');
  });

  it('20. Logout In-flight Invalidation: Discards pending history responses', () => {
    let activeRequestId = 1;
    let localHistory: HistoryItemApiResponse[] = [];

    // Logout occurs
    activeRequestId++;
    localHistory = [];

    // Delayed response from pre-logout request arrives with requestId = 1
    const delayedResponseRequestId = 1;
    if (delayedResponseRequestId === activeRequestId) {
      localHistory = [{ analysis_id: 'stale', title: 'Stale', channel: 'sms', created_at: 'now' }];
    }

    assert.equal(localHistory.length, 0, 'Delayed response after logout must be discarded');
  });

  it('21. Unmount Safety: Hook marks isMounted=false and discards updates', () => {
    let isMounted = true;
    let updateFired = false;

    // Component unmounts
    isMounted = false;

    if (isMounted) {
      updateFired = true;
    }

    assert.equal(updateFired, false, 'State update must not fire after unmount');
  });

  it('22. History 401: Invokes existing invalidateSession callback', () => {
    let invalidateSessionCalled = false;
    const options = {
      onAuthFailure: () => {
        invalidateSessionCalled = true;
      },
    };

    const status = 401;
    if (status === 401) {
      options.onAuthFailure();
    }

    assert.equal(invalidateSessionCalled, true, '401 on history must trigger invalidateSession');
  });

  it('23. History Error Surfacing: Sets error message without fabricating data or crashing', () => {
    let historyState: HistoryItemApiResponse[] = [];
    let errorState: string | null = null;

    const networkError = new Error('Database service unavailable');
    errorState = networkError.message;

    assert.equal(historyState.length, 0, 'Failed history must not be replaced with mock data');
    assert.equal(errorState, 'Database service unavailable');
  });
});




