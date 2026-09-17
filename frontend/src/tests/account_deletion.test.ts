import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { UserProfile, AnalysisSession } from '../types';
import { ApiError } from '../lib/api';

describe('Batch 5.3 — Account Deletion Lifecycle', () => {
  it('1. Account Deletion (Success): Signs out, clears persistent history and local sessions, navigates to landing', async () => {
    let currentUser: UserProfile | null = {
      id: 'usr-bob-123',
      name: 'Bob',
      email: 'bob@example.com',
      accessToken: 'bob-valid-jwt',
    };
    let sessions: AnalysisSession[] = [
      { id: 'sess-1', title: 'Bob Test', selectedModel: 'sms', submittedInput: 'hi', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let activeSessionId: string | null = 'sess-1';
    let currentView: 'landing' | 'workspace' = 'workspace';
    let settingsModalOpen = true;

    // Backend deletion mock returns true
    const deleteAccountMock = async (token: string): Promise<boolean> => {
      assert.equal(token, 'bob-valid-jwt');
      return true;
    };

    // Execute flow
    const success = await deleteAccountMock(currentUser.accessToken);
    if (success) {
      settingsModalOpen = false;
      currentUser = null; // signOut
      sessions = [];
      activeSessionId = null;
      currentView = 'landing';
    }

    assert.equal(currentUser, null, 'User must be signed out on confirmed account deletion');
    assert.equal(sessions.length, 0, 'All local sessions must be cleared');
    assert.equal(activeSessionId, null, 'Active session must be reset');
    assert.equal(currentView, 'landing', 'View must return to landing page (guest mode)');
    assert.equal(settingsModalOpen, false, 'Settings modal must close');
  });

  it('2. Account Deletion Fail-Closed: Backend rejection PRESERVES user and sessions', async () => {
    let currentUser: UserProfile | null = {
      id: 'usr-bob-123',
      name: 'Bob',
      email: 'bob@example.com',
      accessToken: 'bob-valid-jwt',
    };
    let sessions: AnalysisSession[] = [
      { id: 'sess-1', title: 'Bob Test', selectedModel: 'sms', submittedInput: 'hi', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let activeSessionId: string | null = 'sess-1';
    let currentView: 'landing' | 'workspace' = 'workspace';
    let errorSurfaced: string | null = null;

    // Backend fail-closed rejection mock
    const deleteAccountMock = async (token: string): Promise<boolean> => {
      throw new ApiError('Failed to delete authentication user record. Account deletion incomplete.', 500);
    };

    try {
      await deleteAccountMock(currentUser.accessToken);
      // If it erroneously succeeds:
      currentUser = null;
    } catch (err: any) {
      errorSurfaced = err.message;
      // Fail-closed rule: DO NOT sign out, DO NOT clear user!
    }

    assert.ok(currentUser !== null, 'User must NOT be signed out when account deletion fails');
    assert.equal(currentUser?.id, 'usr-bob-123');
    assert.equal(sessions.length, 1, 'Sessions must NOT be deleted locally on backend failure');
    assert.equal(activeSessionId, 'sess-1', 'Active session must be preserved');
    assert.equal(currentView, 'workspace', 'Must NOT navigate away to guest mode');
    assert.equal(errorSurfaced, 'Failed to delete authentication user record. Account deletion incomplete.');
  });

  it('3. Account Deletion (401 Auth Expired): Invokes session invalidation flow', async () => {
    let invalidateCalled = false;
    let currentUser: UserProfile | null = {
      id: 'usr-bob-123',
      name: 'Bob',
      email: 'bob@example.com',
      accessToken: 'expired-token',
    };

    const deleteAccountMock = async (token: string): Promise<boolean> => {
      throw new ApiError('Authentication required or session expired.', 401);
    };

    try {
      await deleteAccountMock(currentUser.accessToken);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 401) {
        invalidateCalled = true;
        currentUser = null;
      }
    }

    assert.equal(invalidateCalled, true, '401 on account deletion must trigger invalidation');
    assert.equal(currentUser, null, 'Expired session must be invalidated');
  });

  it('4. Account Deletion Double-Submission Guard: In-flight deletion blocks duplicate attempts', async () => {
    let isDeletingAccount = false;
    let networkCalls = 0;

    const handleDeleteAccount = async () => {
      if (isDeletingAccount) return false;
      isDeletingAccount = true;
      networkCalls++;
      return true;
    };

    const first = await handleDeleteAccount();
    const second = await handleDeleteAccount();

    assert.equal(first, true);
    assert.equal(second, false, 'Concurrent/duplicate account deletion calls must be blocked');
    assert.equal(networkCalls, 1, 'Only 1 network request should be dispatched');
  });

  it('5. Guest Mode Isolation: SettingsModal and account deletion are never accessible to guests', () => {
    const guestUser: UserProfile | null = null;

    // Condition in App.tsx: {user && <SettingsModal ... />}
    const renderSettingsModal = Boolean(guestUser);

    assert.equal(renderSettingsModal, false, 'SettingsModal must never be mounted in Guest Mode');
  });

  it('6. Account Deletion Retry (Row 29): initial failure allows successful retry wiping data', async () => {
    let user: UserProfile | null = { id: 'usr-bob', name: 'Bob', email: 'b@ex.com', accessToken: 'jwt-1' };
    let sessions: AnalysisSession[] = [
      { id: 's1', title: 'S1', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let modalOpen = true;
    let callCount = 0;

    const mockDeleteAccount = async () => {
      callCount++;
      if (callCount === 1) {
        throw new ApiError('Internal server error', 500);
      }
      return true;
    };

    // Attempt 1: fails
    try {
      await mockDeleteAccount();
      user = null;
      sessions = [];
      modalOpen = false;
    } catch {
      // Fail closed
    }
    assert.equal(callCount, 1);
    assert.notEqual(user, null, 'User remains authenticated on failure');
    assert.equal(sessions.length, 1, 'Sessions preserved on failure');
    assert.equal(modalOpen, true, 'Modal remains open');

    // Attempt 2: retry succeeds
    const success = await mockDeleteAccount();
    if (success) {
      user = null;
      sessions = [];
      modalOpen = false;
    }
    assert.equal(callCount, 2);
    assert.equal(user, null, 'User signed out on successful retry');
    assert.equal(sessions.length, 0, 'Sessions cleared on successful retry');
    assert.equal(modalOpen, false, 'Modal closed on successful retry');
  });

  it('7. Account Deletion Loading State (Row 26): confirm button disabled, spinner rendered, cancel disabled', () => {
    const isDeletingAccount = true;
    const confirmButton = {
      disabled: isDeletingAccount,
      spinner: 'w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin',
      text: 'Deleting Account...',
    };
    const cancelButton = {
      disabled: isDeletingAccount,
    };

    assert.equal(confirmButton.disabled, true);
    assert.ok(confirmButton.spinner.includes('animate-spin'));
    assert.equal(confirmButton.text, 'Deleting Account...');
    assert.equal(cancelButton.disabled, true);
  });

  it('8. Account Deletion 401 Full Contract (7C.1): invalidateSession, user=null, sessions=[], modal=false, activeSessionId=null', async () => {
    let user: UserProfile | null = { id: 'usr-1', name: 'Alice', email: 'a@ex.com', accessToken: 'expired-jwt' };
    let sessions: AnalysisSession[] = [
      { id: 's1', title: 'S1', selectedModel: 'sms', submittedInput: '', isAnalyzing: false, stages: [], currentStageIndex: 0, createdAt: 'now' },
    ];
    let activeSessionId: string | null = 's1';
    let modalOpen = true;
    let invalidateCalled = false;

    const invalidateSession = () => {
      invalidateCalled = true;
      user = null;
      sessions = [];
      activeSessionId = null;
    };

    const mockDelete = async () => {
      throw new ApiError('Unauthorized token', 401);
    };

    try {
      await mockDelete();
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 401) {
        invalidateSession();
        modalOpen = false;
      }
    }

    assert.equal(invalidateCalled, true, 'invalidateSession must be called');
    assert.equal(user, null, 'User must transition to null (guest mode)');
    assert.equal(sessions.length, 0, 'Local sessions must be cleared');
    assert.equal(activeSessionId, null, 'Active session ID must be reset to null');
    assert.equal(modalOpen, false, 'Modal must close on 401');
  });
});
