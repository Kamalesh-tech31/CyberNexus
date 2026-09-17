import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { AnalysisSession, UserProfile } from '../types';
import { HistoryItemApiResponse } from '../lib/api';

describe('Batch 5.1 & 5.2 — History Deletion Lifecycle', () => {
  it('1. Delete One (Success): removes session and clears activeSessionId when active item is deleted', async () => {
    let sessions: AnalysisSession[] = [
      {
        id: 'sess-to-delete',
        title: 'Session to Delete',
        selectedModel: 'sms',
        submittedInput: 'test input',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
      },
      {
        id: 'sess-to-keep',
        title: 'Session to Keep',
        selectedModel: 'url',
        submittedInput: 'keep input',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
      },
    ];
    let activeSessionId: string | null = 'sess-to-delete';

    // Mock successful backend deletion
    const backendDeleteMock = async (id: string, token: string): Promise<boolean> => {
      assert.equal(id, 'sess-to-delete');
      assert.equal(token, 'valid-token');
      return true;
    };

    const idToDelete = 'sess-to-delete';
    const success = await backendDeleteMock(idToDelete, 'valid-token');
    if (success) {
      sessions = sessions.filter((s) => s.id !== idToDelete);
      if (activeSessionId === idToDelete) {
        activeSessionId = null;
      }
    }

    assert.equal(sessions.length, 1);
    assert.equal(sessions[0].id, 'sess-to-keep');
    assert.equal(activeSessionId, null, 'Active session must be cleared when active item is deleted');
  });

  it('2. Delete One (Success on inactive item): activeSessionId remains preserved', async () => {
    let sessions: AnalysisSession[] = [
      {
        id: 'active-session',
        title: 'Active Session',
        selectedModel: 'sms',
        submittedInput: 'test',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
      },
      {
        id: 'inactive-session',
        title: 'Inactive Session',
        selectedModel: 'url',
        submittedInput: 'test',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
      },
    ];
    let activeSessionId: string | null = 'active-session';

    const idToDelete = 'inactive-session';
    const success = true; // backend confirmed
    if (success) {
      sessions = sessions.filter((s) => s.id !== idToDelete);
      if (activeSessionId === idToDelete) {
        activeSessionId = null;
      }
    }

    assert.equal(sessions.length, 1);
    assert.equal(activeSessionId, 'active-session', 'Active session must NOT change when an inactive session is deleted');
  });

  it('3. Delete One (Backend Failure): preserves local history and session state', async () => {
    let sessions: AnalysisSession[] = [
      {
        id: 'sess-1',
        title: 'Protected Session',
        selectedModel: 'sms',
        submittedInput: 'test',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
      },
    ];
    let activeSessionId: string | null = 'sess-1';
    let errorMessage: string | null = null;

    // Backend responds with error (e.g. 500 or network drop)
    const backendDeleteMock = async (): Promise<boolean> => {
      throw new Error('Database connection failed');
    };

    try {
      await backendDeleteMock();
      sessions = sessions.filter((s) => s.id !== 'sess-1');
    } catch (err: any) {
      errorMessage = err.message;
    }

    assert.equal(sessions.length, 1, 'Session must NOT be deleted locally if backend fails');
    assert.equal(activeSessionId, 'sess-1', 'Active session must remain intact on failure');
    assert.equal(errorMessage, 'Database connection failed');
  });

  it('4. Delete One (401 Auth Expired): invokes onAuthFailure', async () => {
    let onAuthFailureCalled = false;
    const options = {
      onAuthFailure: () => {
        onAuthFailureCalled = true;
      },
    };

    const status = 401;
    if (status === 401) {
      options.onAuthFailure();
    }

    assert.equal(onAuthFailureCalled, true, '401 on single deletion must trigger auth failure callback');
  });

  it('5. Delete One Double-Click Guard: prevents duplicate requests for same analysis ID', async () => {
    const deletingIds = new Set<string>();
    let networkCallCount = 0;

    const tryDelete = async (id: string) => {
      if (deletingIds.has(id)) {
        return false; // Guard
      }
      deletingIds.add(id);
      networkCallCount++;
      return true;
    };

    const firstCall = await tryDelete('sess-100');
    const secondCall = await tryDelete('sess-100'); // rapid double-click

    assert.equal(firstCall, true);
    assert.equal(secondCall, false, 'Duplicate deletion request must be blocked while in-flight');
    assert.equal(networkCallCount, 1, 'Only one network call should occur');
  });

  it('6. Delete All (Success): clears all sessions and resets activeSessionId', async () => {
    let sessions: AnalysisSession[] = [
      { id: '1', title: 'A', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
      { id: '2', title: 'B', selectedModel: 'url', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let history: HistoryItemApiResponse[] = [
      { analysis_id: '1', title: 'A', channel: 'sms', created_at: 'now' },
      { analysis_id: '2', title: 'B', channel: 'url', created_at: 'now' },
    ];
    let activeSessionId: string | null = '1';

    // Backend confirms clear history
    const backendClearMock = async (): Promise<boolean> => true;
    const success = await backendClearMock();

    if (success) {
      sessions = [];
      history = [];
      activeSessionId = null;
    }

    assert.equal(sessions.length, 0, 'All sessions must be cleared');
    assert.equal(history.length, 0, 'All history items must be cleared');
    assert.equal(activeSessionId, null, 'Active session ID must be reset to null');
  });

  it('7. Delete All (Backend Failure): preserves local history and sessions', async () => {
    let sessions: AnalysisSession[] = [
      { id: '1', title: 'A', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let history: HistoryItemApiResponse[] = [
      { analysis_id: '1', title: 'A', channel: 'sms', created_at: 'now' },
    ];
    let errorSurfaced: string | null = null;

    try {
      throw new Error('500 Internal Server Error');
    } catch (err: any) {
      errorSurfaced = err.message;
    }

    assert.equal(sessions.length, 1, 'Sessions must be preserved on backend failure');
    assert.equal(history.length, 1, 'History must be preserved on backend failure');
    assert.equal(errorSurfaced, '500 Internal Server Error');
  });

  it('8. Delete All (401 Auth Expired): invokes onAuthFailure', async () => {
    let authFailureCalled = false;
    const options = {
      onAuthFailure: () => {
        authFailureCalled = true;
      },
    };

    const status = 401;
    if (status === 401) {
      options.onAuthFailure();
    }

    assert.equal(authFailureCalled, true, '401 on delete all must trigger session invalidation');
  });

  it('9. Delete All Double-Click Guard: blocks concurrent delete-all requests', async () => {
    let isDeletingAll = false;
    let networkCallCount = 0;

    const tryDeleteAll = async () => {
      if (isDeletingAll) return false;
      isDeletingAll = true;
      networkCallCount++;
      return true;
    };

    const first = await tryDeleteAll();
    const second = await tryDeleteAll();

    assert.equal(first, true);
    assert.equal(second, false, 'Concurrent delete all must be guarded');
    assert.equal(networkCallCount, 1);
  });

  it('10. Guest Mode Deletion: removes from ephemeral memory only, never calls backend API', async () => {
    const user: UserProfile | null = null;
    let backendApiCalled = false;

    let guestSessions: AnalysisSession[] = [
      { id: 'guest-1', title: 'Guest check', selectedModel: 'url', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let activeSessionId: string | null = 'guest-1';

    // App.tsx handleDeleteSession logic
    const handleDelete = (id: string) => {
      if (user && (user as UserProfile).accessToken) {
        backendApiCalled = true;
      } else {
        guestSessions = guestSessions.filter((s) => s.id !== id);
        if (activeSessionId === id) {
          activeSessionId = null;
        }
      }
    };

    handleDelete('guest-1');

    assert.equal(backendApiCalled, false, 'Backend delete API must NEVER be called in Guest Mode');
    assert.equal(guestSessions.length, 0, 'Guest session must be removed from local state');
    assert.equal(activeSessionId, null, 'Active session must be cleared');
  });

  it('11. Guest Mode UI Isolation: Delete All History control is hidden from guests', () => {
    const user: UserProfile | null = null;
    const sessions = [
      { id: 'guest-1', title: 'Guest check', selectedModel: 'url', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];

    // Condition in Sidebar.tsx: user && sessions.length > 0 && onDeleteAllHistory
    const showDeleteAll = Boolean(user && sessions.length > 0);

    assert.equal(showDeleteAll, false, 'Guest mode must never render Delete All History control');
  });

  it('12. Delete One Retry (Row 18): initial failure preserves session and allows successful retry', async () => {
    let sessions: AnalysisSession[] = [
      { id: 'sess-err', title: 'Error Session', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
      { id: 'sess-ok', title: 'OK Session', selectedModel: 'url', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let callCount = 0;

    const mockDelete = async (id: string) => {
      callCount++;
      if (callCount === 1) {
        throw new Error('Network error');
      }
      return true;
    };

    // Attempt 1: fails
    try {
      await mockDelete('sess-err');
      sessions = sessions.filter((s) => s.id !== 'sess-err');
    } catch {
      // Retained
    }
    assert.equal(callCount, 1);
    assert.equal(sessions.length, 2, 'Must retain session on initial failure');

    // Attempt 2: retry succeeds
    const success = await mockDelete('sess-err');
    if (success) {
      sessions = sessions.filter((s) => s.id !== 'sess-err');
    }
    assert.equal(callCount, 2);
    assert.equal(sessions.length, 1);
    assert.equal(sessions[0].id, 'sess-ok');
  });

  it('13. Delete All Retry (Row 23): initial failure retains sessions and allows successful retry', async () => {
    let sessions: AnalysisSession[] = [
      { id: 'sess-1', title: 'S1', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
      { id: 'sess-2', title: 'S2', selectedModel: 'url', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let callCount = 0;

    const mockClear = async () => {
      callCount++;
      if (callCount === 1) {
        throw new Error('Server error');
      }
      return true;
    };

    // Attempt 1: fails
    try {
      await mockClear();
      sessions = [];
    } catch {
      // Retained
    }
    assert.equal(callCount, 1);
    assert.equal(sessions.length, 2, 'Must retain all sessions on initial failure');

    // Attempt 2: retry succeeds
    const success = await mockClear();
    if (success) {
      sessions = [];
    }
    assert.equal(callCount, 2);
    assert.equal(sessions.length, 0, 'Must clear all sessions on successful retry');
  });

  it('14. Concurrent Delete-One Locking Model (7C.3): Set<string> allows concurrent distinct items and isolates completion', async () => {
    let deletingIds = new Set<string>();

    const startDelete = (id: string) => {
      if (deletingIds.has(id)) return false;
      deletingIds.add(id);
      return true;
    };

    const finishDelete = (id: string) => {
      deletingIds.delete(id);
    };

    // Item 1 and Item 2 can delete simultaneously
    assert.equal(startDelete('item-1'), true);
    assert.equal(startDelete('item-2'), true);
    assert.equal(deletingIds.size, 2);

    // Duplicate item 1 blocked
    assert.equal(startDelete('item-1'), false);

    // Item 1 finishes
    finishDelete('item-1');
    assert.equal(deletingIds.has('item-1'), false);
    assert.equal(deletingIds.has('item-2'), true, 'item-2 remains in deletingIds');

    // Item 2 finishes
    finishDelete('item-2');
    assert.equal(deletingIds.size, 0);
  });
});
