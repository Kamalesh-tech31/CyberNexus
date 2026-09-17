import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { AnalysisSession, AnalysisType, UserProfile } from './types';
import { SAMPLE_PRESETS } from './data/mockData';
import { analyzeContent, analyzeQRFile, deleteUserAccount, ApiError } from './lib/api';
import { adaptApiResponseToResult, adaptStoredAnalysisToResult } from './lib/resultAdapter';
import { LandingPage } from './components/LandingPage';
import { AuthModal } from './components/AuthModal';
import { Sidebar } from './components/Sidebar';
import { Workspace } from './components/Workspace';
import { QRUploadModal } from './components/QRUploadModal';
import { SettingsModal } from './components/SettingsModal';
import { useAuthSession } from './hooks/useAuthSession';
import { useHistory, mapHistoryItemToSession } from './hooks/useHistory';

export default function App() {
  // Navigation View: 'landing' | 'workspace'
  const [currentView, setCurrentView] = useState<'landing' | 'workspace'>('landing');

  // Auth Session Hook (encapsulates session restoration, auth state listener, and token management)
  const { user, loading: authLoading, signOut, invalidateSession, setUser } = useAuthSession();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const handleAuthFailure = useCallback(() => {
    invalidateSession();
  }, [invalidateSession]);

  const historyOptions = useMemo(
    () => ({
      onAuthFailure: handleAuthFailure,
    }),
    [handleAuthFailure]
  );

  // Persistent History Hook (manages backend GET /api/history hydration and identity binding)
  const {
    loading: historyLoading,
    error: historyError,
    deletingIds,
    isDeletingAll,
    fetchHistory,
    fetchAnalysisDetail,
    deleteAnalysis,
    clearAllUserHistory,
    clearHistory,
    addHistoryItem,
  } = useHistory(historyOptions);

  // Workspace & Session State (Fresh application load starts with empty history until Phase 6F-2 persistence)
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Track the last access token that triggered history hydration to prevent redundant loops
  const lastHydratedTokenRef = useRef<string | null>(null);

  // Track previous authenticated user ID to isolate Guest, User A, and User B states
  const prevUserRef = useRef<{ id: string | null; initialized: boolean }>({
    id: null,
    initialized: false,
  });

  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const currentUserRef = useRef<UserProfile | null>(user);
  useEffect(() => {
    currentUserRef.current = user;
  }, [user]);

  const activeAnalysisRequestIdRef = useRef(0);

  // Handle deterministic auth transitions (Guest -> Auth, Auth -> Logout, User A -> User B)
  useEffect(() => {
    if (authLoading) {
      // Still restoring session from Supabase; do not trigger transition cleanup prematurely
      return;
    }

    const currentId = user?.id || null;

    if (!prevUserRef.current.initialized) {
      // Initial session restoration complete
      prevUserRef.current = { id: currentId, initialized: true };
      return;
    }

    const previousId = prevUserRef.current.id;

    if (previousId !== currentId) {
      // State boundary transition:
      // 1. Guest -> Authenticated: discard ephemeral guest sessions
      // 2. Authenticated -> Guest (Logout): clear user local history
      // 3. User A -> User B: clear User A's sessions, clean start for User B
      lastHydratedTokenRef.current = null;
      setSessions([]);
      setActiveSessionId(null);
      setUploadedImage(null);
      setSelectedModel('auto');
      pendingApiResultsRef.current.clear();
      clearHistory();

      prevUserRef.current = { id: currentId, initialized: true };
    }
  }, [user, authLoading, clearHistory]);

  // Hydrate authenticated user history from backend
  useEffect(() => {
    if (authLoading) {
      // Wait for session restoration to complete
      return;
    }

    if (user?.accessToken) {
      if (lastHydratedTokenRef.current === user.accessToken) {
        return;
      }
      lastHydratedTokenRef.current = user.accessToken;

      fetchHistory(user.accessToken).then((fetchedHistory) => {
        if (!isMountedRef.current) return;
        if (fetchedHistory) {
          setSessions((prev) => {
            const resultMap = new Map<string, AnalysisSession>();
            for (const s of prev) {
              if (s.result) {
                resultMap.set(s.id, s);
              }
            }
            return fetchedHistory.map((item) => {
              const existing = resultMap.get(item.analysis_id);
              if (existing) return existing;
              return mapHistoryItemToSession(item);
            });
          });
        }
      });
    } else {
      // Guest mode: clear persistent history
      lastHydratedTokenRef.current = null;
      clearHistory();
    }
  }, [user?.id, user?.accessToken, authLoading, fetchHistory, clearHistory]);

  // If user signs in while on landing, navigate to workspace
  useEffect(() => {
    if (user && currentView === 'landing') {
      setCurrentView('workspace');
    }
  }, [user, currentView]);

  // Composer State
  const [selectedModel, setSelectedModel] = useState<AnalysisType>('auto');
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // Active Session derived
  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  // Track pending API responses
  const pendingApiResultsRef = useRef<Map<string, { result?: any; error?: string }>>(new Map());

  // Keyboard shortcut for New Analysis (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        handleNewAnalysis();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Execution Stage Progression Timer
  useEffect(() => {
    if (!activeSession || !activeSession.isAnalyzing) return;

    const totalStages = activeSession.stages.length;
    const stageDuration = 450; // ms per stage for smooth responsive feedback

    const timer = setTimeout(() => {
      setSessions((prevSessions) =>
        prevSessions.map((s) => {
          if (s.id !== activeSession.id) return s;

          const pending = pendingApiResultsRef.current.get(s.id);
          const nextIndex = s.currentStageIndex + 1;

          if (nextIndex < totalStages) {
            // Update stages status
            const updatedStages = s.stages.map((st, idx) => ({
              ...st,
              status: (idx < nextIndex ? 'completed' : (idx === nextIndex ? 'running' : 'pending')) as any
            }));
            return {
              ...s,
              currentStageIndex: nextIndex,
              stages: updatedStages
            };
          } else {
            // Reached final stage - check if API result is ready
            if (pending?.error) {
              return {
                ...s,
                isAnalyzing: false,
                currentStageIndex: totalStages,
                error: pending.error,
                stages: s.stages.map((st) => ({ ...st, status: 'completed' as const }))
              };
            } else if (pending?.result) {
              return {
                ...s,
                isAnalyzing: false,
                currentStageIndex: totalStages,
                result: pending.result,
                stages: s.stages.map((st) => ({ ...st, status: 'completed' as const }))
              };
            } else {
              // Wait on last stage for API response to return
              return {
                ...s,
                currentStageIndex: totalStages - 1,
                stages: s.stages.map((st, idx) => ({
                  ...st,
                  status: idx < totalStages - 1 ? 'completed' : 'running'
                }))
              };
            }
          }
        })
      );
    }, stageDuration);

    return () => clearTimeout(timer);
  }, [activeSession?.isAnalyzing, activeSession?.currentStageIndex, activeSession?.id]);

  // Handler: Start from Landing Page (Enters Guest Mode if not signed in)
  const handleGetStarted = () => {
    // If not authenticated, user remains null (Guest Mode)
    setCurrentView('workspace');
    setActiveSessionId(null);
  };

  const handleOpenSignIn = () => {
    setAuthModalOpen(true);
  };

  const handleSignOut = async () => {
    await signOut();
    clearHistory();
    setSessions([]);
    setActiveSessionId(null);
    setUploadedImage(null);
    setSelectedModel('auto');
    pendingApiResultsRef.current.clear();
    setCurrentView('landing');
  };

  // Handler: New Analysis (clears session and returns to composer empty state)
  const handleNewAnalysis = () => {
    setActiveSessionId(null);
    setSelectedModel('auto');
    setUploadedImage(null);
  };

  // Handler: Select a historical session
  const handleSelectSession = async (id: string) => {
    setActiveSessionId(id);
    const selected = sessions.find((s) => s.id === id);
    if (!selected) return;

    setSelectedModel(selected.selectedModel);
    setUploadedImage(selected.uploadedImage || null);

    // If session already has result, is currently analyzing, or is loading detail, nothing to fetch
    if (selected.result || selected.isAnalyzing || selected.isLoadingDetail) {
      return;
    }

    // Authenticated user with placeholder session: fetch full analysis detail from backend
    if (user?.accessToken) {
      const requestingUserId = currentUserRef.current?.id || null;
      setSessions((prev) =>
        prev.map((s) => (s.id === id ? { ...s, isLoadingDetail: true, error: undefined } : s))
      );

      try {
        const detail = await fetchAnalysisDetail(id, user.accessToken);
        if (!isMountedRef.current || (currentUserRef.current?.id || null) !== requestingUserId) {
          return;
        }
        if (detail) {
          const { result, submittedInput, selectedModel: resolvedModel } = adaptStoredAnalysisToResult(detail);
          setSessions((prev) =>
            prev.map((s) =>
              s.id === id
                ? {
                    ...s,
                    isLoadingDetail: false,
                    result,
                    submittedInput: submittedInput || s.submittedInput,
                    selectedModel: resolvedModel || s.selectedModel,
                    title: s.title || detail.title,
                  }
                : s
            )
          );
          setSelectedModel(resolvedModel);
        } else {
          setSessions((prev) =>
            prev.map((s) =>
              s.id === id
                ? {
                    ...s,
                    isLoadingDetail: false,
                    error: s.error || 'Failed to load historical analysis detail.',
                  }
                : s
            )
          );
        }
      } catch (err: any) {
        if (!isMountedRef.current || (currentUserRef.current?.id || null) !== requestingUserId) {
          return;
        }
        setSessions((prev) =>
          prev.map((s) =>
            s.id === id
              ? {
                  ...s,
                  isLoadingDetail: false,
                  error: err?.message || 'Failed to load historical analysis detail.',
                }
              : s
          )
        );
      }
    }
  };

  // Handler: Delete a session
  const handleDeleteSession = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    if (user?.accessToken) {
      const success = await deleteAnalysis(id, user.accessToken);
      if (success) {
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeSessionId === id) {
          setActiveSessionId(null);
        }
      }
    } else {
      // Guest mode: ephemeral memory deletion
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        setActiveSessionId(null);
      }
    }
  };

  // Handler: Delete all history
  const handleDeleteAllHistory = async () => {
    if (!user?.accessToken) return;

    const success = await clearAllUserHistory(user.accessToken);
    if (success) {
      setSessions([]);
      setActiveSessionId(null);
    }
  };

  // Handler: Delete authenticated user account (fail-closed)
  const handleDeleteAccount = async (): Promise<void> => {
    if (!user?.accessToken) return;

    try {
      // Execute fail-closed backend deletion (throws on non-200)
      await deleteUserAccount(user.accessToken);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 401) {
        invalidateSession();
        setSettingsModalOpen(false);
        return;
      }
      throw err;
    }

    // On confirmed backend success: transition to clean guest mode
    setSettingsModalOpen(false);
    await signOut();
    clearHistory();
    setSessions([]);
    setActiveSessionId(null);
    setUploadedImage(null);
    setSelectedModel('auto');
    pendingApiResultsRef.current.clear();
    setCurrentView('landing');
  };

  // Handler: Submit input for analysis via real backend API
  const handleSubmitInput = useCallback((input: string, explicitModel: AnalysisType, image?: string | null, subject?: string | null) => {
    if (activeSession?.isAnalyzing) {
      return;
    }

    const submittingUserId = currentUserRef.current?.id || null;
    const reqId = ++activeAnalysisRequestIdRef.current;

    const newSessionId = `session-${Date.now()}`;
    const title = input.trim().length > 0 
      ? (input.trim().slice(0, 35) + (input.trim().length > 35 ? '...' : ''))
      : (image ? 'QR Code Matrix Analysis' : 'Security Analysis');

    const defaultStages = explicitModel === 'qr'
      ? [
          { id: '1', label: 'QR Optical Matrix Decoding', status: 'running' as const, detail: 'Parsing QR pattern, format, and Reed-Solomon error correction' },
          { id: '2', label: 'Payload Semantic Classification', status: 'pending' as const, detail: 'Detecting URL, Wi-Fi, vCard, or textual schema' },
          { id: '3', label: 'ML Threat Model Evaluation', status: 'pending' as const, detail: 'Routing to calibrated classifier under locked operational threshold' },
          { id: '4', label: 'Model-Grounded Attribution Mapping', status: 'pending' as const, detail: 'Generating progressive disclosure explainability' }
        ]
      : [
          { id: '1', label: 'Lexical & Structural Feature Extraction', status: 'running' as const, detail: 'Parsing tokens, links, and length distributions' },
          { id: '2', label: 'TF-IDF Linguistic Signal Analysis', status: 'pending' as const, detail: 'Evaluating word-level threat attribution' },
          { id: '3', label: 'Calibrated Classifier Probability Scaling', status: 'pending' as const, detail: 'Applying Platt sigmoid scaling' },
          { id: '4', label: 'Model-Grounded Attribution Mapping', status: 'pending' as const, detail: 'Generating progressive disclosure explainability' }
        ];

    const newSession: AnalysisSession = {
      id: newSessionId,
      title: title,
      selectedModel: explicitModel,
      submittedInput: input || (image ? 'QR Code Matrix Image' : 'Security Analysis'),
      uploadedImage: image,
      isAnalyzing: true,
      stages: defaultStages,
      currentStageIndex: 0,
      result: undefined,
      error: undefined,
      createdAt: 'Just now'
    };

    // Prepend to sessions list so it appears at top of history
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSessionId);
    setUploadedImage(null);

    // Determine API call strategy: QR with image → dedicated multipart endpoint
    let apiPromise: Promise<import('./lib/api').AnalysisApiResponse>;

    if (explicitModel === 'qr' && image) {
      // Convert data URL to Blob for multipart upload
      const dataUrlToBlob = (dataUrl: string): Blob => {
        const [header, base64Data] = dataUrl.split(',');
        const mimeMatch = header.match(/:(.*?);/);
        const mime = mimeMatch ? mimeMatch[1] : 'image/png';
        const byteString = atob(base64Data);
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i++) {
          ia[i] = byteString.charCodeAt(i);
        }
        return new Blob([ab], { type: mime });
      };

      const blob = dataUrlToBlob(image);
      const file = new File([blob], 'qr-upload.png', { type: blob.type });
      apiPromise = analyzeQRFile(file, user?.accessToken);
    } else {
      // General text-based analysis endpoint
      const effectiveInput = input || (image || '');
      apiPromise = analyzeContent(
        {
          channel: explicitModel,
          input: effectiveInput,
          subject: subject || null,
        },
        user?.accessToken
      );
    }

    apiPromise
      .then((apiResponse) => {
        if (
          !isMountedRef.current ||
          activeAnalysisRequestIdRef.current !== reqId ||
          (currentUserRef.current?.id || null) !== submittingUserId
        ) {
          return;
        }

        const persistedId = (user?.accessToken && apiResponse.analysis_id) ? apiResponse.analysis_id : newSessionId;
        const persistedCreatedAt = (user?.accessToken && apiResponse.created_at) ? apiResponse.created_at : 'Just now';

        const adaptedResult = adaptApiResponseToResult(apiResponse, input || (image ? 'QR Code Image' : ''), persistedId);
        pendingApiResultsRef.current.set(persistedId, { result: adaptedResult });
        if (persistedId !== newSessionId) {
          pendingApiResultsRef.current.set(newSessionId, { result: adaptedResult });
        }

        // Update session state with real API result and backend-confirmed identity
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== newSessionId && s.id !== persistedId) return s;
            return {
              ...s,
              id: persistedId,
              result: adaptedResult,
              title: s.title || `${adaptedResult.detectedType.toUpperCase()}: ${adaptedResult.verdict}`,
              createdAt: persistedCreatedAt,
            };
          })
        );

        setActiveSessionId((currentActive) => (currentActive === newSessionId ? persistedId : currentActive));

        // If authenticated, sync with persistent history immediately
        if (user?.accessToken && apiResponse.analysis_id && apiResponse.created_at) {
          addHistoryItem({
            analysis_id: apiResponse.analysis_id,
            title: title || `${adaptedResult.detectedType.toUpperCase()}: ${adaptedResult.verdict}`,
            channel: apiResponse.resolved_channel || apiResponse.channel || explicitModel,
            created_at: apiResponse.created_at,
          });
        }
      })
      .catch((err: any) => {
        if (
          !isMountedRef.current ||
          activeAnalysisRequestIdRef.current !== reqId ||
          (currentUserRef.current?.id || null) !== submittingUserId
        ) {
          return;
        }

        const isAuthError = err instanceof ApiError && err.status === 401;
        const errorMsg = isAuthError
          ? 'Authentication session has expired or is invalid. Returned to guest mode.'
          : (err instanceof ApiError ? err.message : (err?.message || 'Analysis request failed.'));
        pendingApiResultsRef.current.set(newSessionId, { error: errorMsg });

        if (isAuthError) {
          invalidateSession();
        }

        // Immediately set error on session
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== newSessionId) return s;
            return {
              ...s,
              isAnalyzing: false,
              error: errorMsg,
            };
          })
        );
      });
  }, [user, activeSession?.isAnalyzing, invalidateSession, addHistoryItem]);

  // Handler: Retry an analysis that previously failed
  const handleRetryAnalysis = () => {
    if (!activeSession || activeSession.isAnalyzing) return;
    handleSubmitInput(
      activeSession.submittedInput,
      activeSession.selectedModel,
      activeSession.uploadedImage
    );
  };

  // Handler: Retry loading historical analysis detail that previously failed
  const handleRetryHistoricalDetail = () => {
    if (!activeSessionId) return;
    const current = sessions.find((s) => s.id === activeSessionId);
    if (!current || current.isLoadingDetail) return;
    handleSelectSession(activeSessionId);
  };

  // Handler: Select a sample test preset
  const handleSelectPreset = (presetId: string) => {
    const preset = SAMPLE_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    setSelectedModel(preset.type);
    handleSubmitInput(preset.input, preset.type, preset.image);
  };

  // Handler: Skip execution animation instantly
  const handleSkipAnimation = () => {
    if (!activeSession) return;
    const pending = pendingApiResultsRef.current.get(activeSession.id);
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSession.id) return s;
        return {
          ...s,
          isAnalyzing: false,
          currentStageIndex: s.stages.length,
          result: pending?.result || s.result,
          error: pending?.error || s.error,
          stages: s.stages.map((st) => ({ ...st, status: 'completed' as const }))
        };
      })
    );
  };

  // Handler: Upload QR from Modal
  const handleSelectQR = (imageData: string, label: string) => {
    setUploadedImage(imageData);
    setSelectedModel('qr');
  };

  return (
    <div className="min-h-screen bg-[#0B0C0A] text-[#EDEDE9] flex flex-col font-sans">
      {/* LANDING PAGE VIEW */}
      {currentView === 'landing' && (
        <LandingPage
          onGetStarted={handleGetStarted}
          onSignIn={handleOpenSignIn}
        />
      )}

      {/* ANALYSIS WORKSPACE VIEW */}
      {currentView === 'workspace' && (
        <div className="flex h-screen w-screen overflow-hidden">
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            isOpen={sidebarOpen}
            isLoadingHistory={historyLoading}
            historyError={historyError}
            deletingIds={deletingIds}
            isDeletingAll={isDeletingAll}
            onDeleteAllHistory={handleDeleteAllHistory}
            onRetryHistory={() => {
              if (historyLoading || !user?.accessToken) return;
              fetchHistory(user.accessToken).then((fetchedHistory) => {
                if (!isMountedRef.current) return;
                if (fetchedHistory) {
                  setSessions((prev) => {
                    const resultMap = new Map<string, AnalysisSession>();
                    for (const s of prev) {
                      if (s.result) {
                        resultMap.set(s.id, s);
                      }
                    }
                    return fetchedHistory.map((item) => {
                      const existing = resultMap.get(item.analysis_id);
                      if (existing) return existing;
                      return mapHistoryItemToSession(item);
                    });
                  });
                }
              });
            }}
            onToggleOpen={() => setSidebarOpen(!sidebarOpen)}
            onSelectSession={handleSelectSession}
            onNewAnalysis={handleNewAnalysis}
            onDeleteSession={handleDeleteSession}
            user={user}
            onSignOut={handleSignOut}
            onOpenSettings={() => setSettingsModalOpen(true)}
            onSignIn={handleOpenSignIn}
          />

          <Workspace
            session={activeSession}
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
            onNewAnalysis={handleNewAnalysis}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
            onSubmitInput={handleSubmitInput}
            onOpenQRModal={() => setQrModalOpen(true)}
            uploadedImage={uploadedImage}
            onRemoveUploadedImage={() => setUploadedImage(null)}
            onSelectPreset={handleSelectPreset}
            onSkipExecutionAnimation={handleSkipAnimation}
            onRetryAnalysis={handleRetryAnalysis}
            onRetryHistoricalDetail={handleRetryHistoricalDetail}
            user={user}
            onSignIn={handleOpenSignIn}
          />
        </div>
      )}

      {/* MODALS */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />

      <QRUploadModal
        isOpen={qrModalOpen}
        onClose={() => setQrModalOpen(false)}
        onSelectQR={handleSelectQR}
      />

      {user && (
        <SettingsModal
          isOpen={settingsModalOpen}
          onClose={() => setSettingsModalOpen(false)}
          user={user}
          onUpdateUser={(updated) => setUser(updated)}
          onDeleteAccount={handleDeleteAccount}
        />
      )}
    </div>
  );
}
