import React, { useRef, useEffect } from 'react';
import { 
  PanelLeft, 
  Plus, 
  RotateCcw, 
  Sparkles, 
  Mail, 
  MessageSquare, 
  Link2, 
  QrCode, 
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  User
} from 'lucide-react';
import { AnalysisSession, AnalysisType, UserProfile } from '../types';
import { Composer } from './Composer';
import { ExecutionState } from './ExecutionState';
import { AnalysisResultView } from './AnalysisResultView';
import { SAMPLE_PRESETS } from '../data/mockData';

interface WorkspaceProps {
  session: AnalysisSession | null;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onNewAnalysis: () => void;
  selectedModel: AnalysisType;
  onSelectModel: (model: AnalysisType) => void;
  onSubmitInput: (input: string, explicitModel: AnalysisType, uploadedImage?: string | null, subject?: string | null) => void;
  onOpenQRModal: () => void;
  uploadedImage: string | null;
  onRemoveUploadedImage: () => void;
  onSelectPreset: (presetId: string) => void;
  onSkipExecutionAnimation: () => void;
  onRetryAnalysis?: () => void;
  onRetryHistoricalDetail?: () => void;
  user: UserProfile | null;
  onSignIn?: () => void;
}

export const Workspace: React.FC<WorkspaceProps> = ({
  session,
  sidebarOpen,
  onToggleSidebar,
  onNewAnalysis,
  selectedModel,
  onSelectModel,
  onSubmitInput,
  onOpenQRModal,
  uploadedImage,
  onRemoveUploadedImage,
  onSelectPreset,
  onSkipExecutionAnimation,
  onRetryAnalysis,
  onRetryHistoricalDetail,
  user,
  onSignIn,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto scroll down when new stages or results appear
  useEffect(() => {
    if (session && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [session?.isAnalyzing, session?.currentStageIndex, session?.result]);

  return (
    <main id="analysis-workspace" className="flex-1 flex flex-col h-screen bg-[#0B0C0A] overflow-hidden relative selection:bg-[#B7D93D]/20 selection:text-[#B7D93D]">
      {/* Top Navbar */}
      <header className="h-14 border-b border-white/5 px-4 sm:px-6 flex items-center justify-between shrink-0 bg-[#0B0C0A]/80 backdrop-blur-xs z-10">
        <div className="flex items-center gap-3">
          {/* Sidebar Toggle button if sidebar is collapsed or on mobile */}
          {!sidebarOpen && (
            <button
              id="workspace-open-sidebar-btn"
              onClick={onToggleSidebar}
              title="Open sidebar"
              className="text-[#9E9E98] hover:text-[#EDEDE9] p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}

          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#B7D93D]" />
            <span className="text-xs font-medium tracking-tight text-[#EDEDE9]">
              CyberNexus
            </span>
          </div>

          {session && (
            <>
              <span className="text-[#666660] text-xs">/</span>
              <span className="text-xs text-[#9E9E98] truncate max-w-[180px] sm:max-w-xs font-normal">
                {session.title}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {session && (
            <button
              id="workspace-new-analysis-header-btn"
              onClick={onNewAnalysis}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-[#EDEDE9] transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-[#B7D93D]" />
              <span className="hidden sm:inline">New</span>
            </button>
          )}

          {!user && onSignIn && (
            <button
              id="workspace-guest-signin-btn"
              onClick={onSignIn}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#B7D93D] text-[#0B0C0A] hover:bg-[#C6E74B] text-xs font-medium transition-colors"
            >
              <span>Sign In</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 sm:px-6 py-6"
      >
        {/* VIEW 1: EMPTY STATE (NEW ANALYSIS) */}
        {!session ? (
          <div className="w-full max-w-2xl mx-auto min-h-[calc(100vh-18rem)] flex flex-col items-center justify-center text-center px-4 animate-in fade-in duration-300">
            {/* Minimal Brand Mark */}
            <div className="w-2 h-2 rounded-full bg-[#B7D93D] mb-4" />

            <div className="text-xs font-mono uppercase tracking-widest text-[#666660] mb-2">
              CyberNexus Intelligence
            </div>

            <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#EDEDE9] mb-3">
              What would you like to analyze?
            </h2>

            <p className="text-sm sm:text-base text-[#9E9E98] max-w-md font-normal leading-relaxed mb-8">
              Analyze an email, message, URL or QR code using machine learning.
            </p>

            {/* Quick Test Preset Pills for Rapid Review & Demonstration */}
            <div className="w-full max-w-xl text-left space-y-2.5">
              <div className="text-[11px] font-mono uppercase tracking-wider text-[#666660] px-1 text-center sm:text-left">
                Test with verified samples:
              </div>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SAMPLE_PRESETS.slice(0, 4).map((preset) => {
                  return (
                    <button
                      key={preset.id}
                      onClick={() => onSelectPreset(preset.id)}
                      className="p-3 rounded-xl bg-[#161715] hover:bg-[#1C1E1A] border border-white/5 hover:border-[#B7D93D]/30 transition-all text-left group flex flex-col justify-between"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-[#EDEDE9] group-hover:text-[#B7D93D] transition-colors">
                          {preset.title}
                        </span>
                        <span className="text-[10px] font-mono text-[#666660] bg-white/5 px-1.5 py-0.5 rounded">
                          {preset.type.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#9E9E98] line-clamp-1">
                        {preset.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          /* VIEW 2: ACTIVE ANALYSIS SESSION (Conversation Style) */
          <div className="w-full max-w-3xl mx-auto space-y-6 pb-20 animate-in fade-in duration-200">
            {/* USER INPUT BLOCK ("You") */}
            <div className="flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#161715] border border-white/10 flex items-center justify-center text-xs font-medium text-[#9E9E98] shrink-0 mt-0.5">
                <User className="w-4 h-4" />
              </div>

              <div className="flex-1 space-y-2 min-w-0">
                <div className="text-xs font-medium text-[#9E9E98]">
                  You
                </div>

                {/* Submitted text content or QR preview */}
                <div className="p-4 rounded-2xl bg-[#161715] border border-white/5 text-sm text-[#EDEDE9] leading-relaxed whitespace-pre-wrap break-words font-sans">
                  {session.uploadedImage && (
                    <div className="mb-3 p-2.5 rounded-xl bg-black/40 border border-white/5 inline-flex items-center gap-3">
                      <QrCode className="w-5 h-5 text-[#B7D93D]" />
                      <div className="text-xs text-[#EDEDE9] font-mono">
                        {session.uploadedImage.startsWith('data:') ? 'Custom QR Code Image' : 'Sample QR Matrix Payload'}
                      </div>
                    </div>
                  )}
                  {session.isLoadingDetail && !session.submittedInput ? (
                    <span className="text-[#666660] italic">Loading original input...</span>
                  ) : (
                    session.submittedInput
                  )}
                </div>
              </div>
            </div>

            {/* CYBERNEXUS RESPONSE BLOCK */}
            <div className="flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#1C1E1A] border border-[#B7D93D]/30 flex items-center justify-center text-xs font-medium text-[#B7D93D] shrink-0 mt-0.5">
                <span className="w-2 h-2 rounded-full bg-[#B7D93D]" />
              </div>

              <div className="flex-1 space-y-4 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-[#EDEDE9]">
                    CyberNexus
                  </span>
                  <span className="text-[10px] font-mono text-[#666660]">
                    ML Pipeline
                  </span>
                </div>

                {/* State A: Execution in progress */}
                {session.isAnalyzing && (
                  <ExecutionState
                    stages={session.stages}
                    currentStageIndex={session.currentStageIndex}
                    detectedType={session.selectedModel === 'auto' ? undefined : session.selectedModel.toUpperCase()}
                    onSkip={onSkipExecutionAnimation}
                  />
                )}

                {/* State B: Historical Detail Loading */}
                {session.isLoadingDetail && (
                  <div className="p-8 rounded-2xl bg-[#161715] border border-white/5 flex flex-col items-center justify-center text-center space-y-3 animate-in fade-in duration-150">
                    <div className="w-5 h-5 border-2 border-[#B7D93D] border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs text-[#9E9E98]">Loading historical analysis detail...</span>
                  </div>
                )}

                {/* State C: Analysis Result Ready */}
                {!session.isAnalyzing && !session.isLoadingDetail && session.result && (
                  <AnalysisResultView result={session.result} />
                )}

                {/* State D: Analysis or Historical Detail Error */}
                {!session.isAnalyzing && !session.isLoadingDetail && session.error && (
                  <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-800/30 text-rose-300 text-xs space-y-3">
                    <div className="flex items-center gap-2 font-medium text-rose-400">
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                      <span>{session.stages.length > 0 ? 'Analysis Error' : 'Historical Analysis Error'}</span>
                    </div>
                    <p className="text-[#EDEDE9]/90 leading-relaxed">
                      {session.error}
                    </p>
                    {/* Retry Analysis Button */}
                    {session.stages.length > 0 && onRetryAnalysis && (
                      <div>
                        <button
                          id="workspace-retry-analysis-btn"
                          onClick={onRetryAnalysis}
                          disabled={session.isAnalyzing}
                          className="px-3 py-1.5 rounded-lg bg-rose-900/40 hover:bg-rose-900/60 text-rose-200 border border-rose-700/50 text-xs font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>{session.isAnalyzing ? 'Analyzing...' : 'Retry Analysis'}</span>
                        </button>
                      </div>
                    )}
                    {/* Retry Historical Detail Button */}
                    {session.stages.length === 0 && onRetryHistoricalDetail && (
                      <div>
                        <button
                          id="workspace-retry-detail-btn"
                          onClick={onRetryHistoricalDetail}
                          disabled={session.isLoadingDetail}
                          className="px-3 py-1.5 rounded-lg bg-rose-900/40 hover:bg-rose-900/60 text-rose-200 border border-rose-700/50 text-xs font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>{session.isLoadingDetail ? 'Loading...' : 'Retry Loading Detail'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Persistent ChatGPT-style Composer */}
      <Composer
        selectedModel={selectedModel}
        onSelectModel={onSelectModel}
        onSubmit={onSubmitInput}
        onOpenQRUpload={onOpenQRModal}
        uploadedImage={uploadedImage}
        onRemoveUploadedImage={onRemoveUploadedImage}
        isAnalyzing={session?.isAnalyzing || false}
      />
    </main>
  );
};
