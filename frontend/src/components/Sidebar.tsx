import React, { useState, useRef, useEffect } from 'react';
import { 
  Plus, 
  PanelLeftClose, 
  PanelLeft, 
  Mail, 
  MessageSquare, 
  Link2, 
  QrCode, 
  Trash2, 
  MoreVertical, 
  LogOut, 
  Settings, 
  User, 
  Sparkles,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import { AnalysisSession, UserProfile } from '../types';

interface SidebarProps {
  sessions: AnalysisSession[];
  activeSessionId: string | null;
  isOpen: boolean;
  isLoadingHistory?: boolean;
  historyError?: string | null;
  onRetryHistory?: () => void;
  onToggleOpen: () => void;
  onSelectSession: (id: string) => void;
  onNewAnalysis: () => void;
  deletingIds?: Set<string>;
  isDeletingAll?: boolean;
  onDeleteAllHistory?: () => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  user: UserProfile | null;
  onSignOut: () => void;
  onOpenSettings: () => void;
  onSignIn?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  isOpen,
  isLoadingHistory = false,
  historyError = null,
  onRetryHistory,
  onToggleOpen,
  onSelectSession,
  onNewAnalysis,
  deletingIds,
  isDeletingAll = false,
  onDeleteAllHistory,
  onDeleteSession,
  user,
  onSignOut,
  onOpenSettings,
  onSignIn,
}) => {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [confirmingDeleteAll, setConfirmingDeleteAll] = useState<boolean>(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  // Close profile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    };
    if (profileMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [profileMenuOpen]);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <Mail className="w-3.5 h-3.5 text-[#9E9E98]" />;
      case 'sms':
        return <MessageSquare className="w-3.5 h-3.5 text-[#9E9E98]" />;
      case 'url':
        return <Link2 className="w-3.5 h-3.5 text-[#9E9E98]" />;
      case 'qr':
        return <QrCode className="w-3.5 h-3.5 text-[#9E9E98]" />;
      default:
        return <ShieldCheck className="w-3.5 h-3.5 text-[#9E9E98]" />;
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          onClick={onToggleOpen}
          className="md:hidden fixed inset-0 bg-black/60 z-30 backdrop-blur-xs"
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed md:static inset-y-0 left-0 z-40 bg-[#10110F] border-r border-white/5 flex flex-col justify-between transition-all duration-200 ease-in-out select-none ${
          isOpen ? 'w-64 translate-x-0' : 'w-0 -translate-x-full md:translate-x-0 md:w-0 overflow-hidden'
        }`}
        style={{ minWidth: isOpen ? '16rem' : '0' }}
      >
        {/* Top Header & New Analysis */}
        <div className="p-4 flex flex-col gap-4">
          {/* Brand Header & Collapse Icon */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-full bg-[#B7D93D]" />
              <span className="font-semibold text-sm tracking-tight text-[#EDEDE9]">
                CyberNexus
              </span>
            </div>

            <button
              id="sidebar-collapse-btn"
              onClick={onToggleOpen}
              title="Collapse sidebar"
              className="text-[#9E9E98] hover:text-[#EDEDE9] hover:bg-white/5 p-1.5 rounded-lg transition-colors"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          {/* New Analysis Button */}
          <button
            id="sidebar-new-analysis-btn"
            onClick={onNewAnalysis}
            className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl bg-[#161715] hover:bg-[#1C1E1A] text-[#EDEDE9] border border-white/5 hover:border-[#B7D93D]/30 transition-all text-xs font-medium group"
          >
            <div className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-[#B7D93D] group-hover:scale-110 transition-transform" />
              <span>New Analysis</span>
            </div>
            <span className="text-[10px] font-mono text-[#666660] bg-white/5 px-1.5 py-0.5 rounded">
              ⌘K
            </span>
          </button>
        </div>

        {/* Middle: History List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#666660]">
              History
            </span>
            {user && sessions.length > 0 && onDeleteAllHistory && (
              confirmingDeleteAll ? (
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  <button
                    id="sidebar-confirm-delete-all-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteAllHistory();
                      setConfirmingDeleteAll(false);
                    }}
                    disabled={isDeletingAll}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-red-950/70 border border-red-800/60 text-red-300 hover:bg-red-900/60 font-mono transition-colors"
                  >
                    {isDeletingAll ? 'Clearing...' : 'Confirm All'}
                  </button>
                  <button
                    id="sidebar-cancel-delete-all-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmingDeleteAll(false);
                    }}
                    className="text-[10px] px-1 py-0.5 rounded bg-white/5 text-[#9E9E98] hover:bg-white/10"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <button
                  id="sidebar-clear-all-btn"
                  onClick={() => setConfirmingDeleteAll(true)}
                  className="text-[10px] text-[#666660] hover:text-red-400 transition-colors"
                  title="Clear all analysis history"
                >
                  Clear All
                </button>
              )
            )}
          </div>

          {historyError && sessions.length > 0 && (
            <div className="mx-3 mb-2 p-2 rounded bg-rose-950/20 border border-rose-800/30 text-rose-300 text-[11px] flex items-center justify-between">
              <span>Failed to refresh history</span>
              {onRetryHistory && (
                <button
                  onClick={onRetryHistory}
                  disabled={isLoadingHistory}
                  className="text-[#B7D93D] hover:underline cursor-pointer disabled:opacity-50 ml-2"
                >
                  {isLoadingHistory ? 'Retrying...' : 'Retry'}
                </button>
              )}
            </div>
          )}

          {isLoadingHistory && sessions.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[#666660] flex items-center justify-center gap-2">
              <div className="w-3.5 h-3.5 border-2 border-[#B7D93D] border-t-transparent rounded-full animate-spin" />
              <span>Loading history...</span>
            </div>
          ) : historyError && sessions.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-red-400 space-y-2">
              <div>Failed to load history</div>
              {onRetryHistory && (
                <button
                  onClick={onRetryHistory}
                  disabled={isLoadingHistory}
                  className="text-[11px] text-[#B7D93D] hover:underline cursor-pointer disabled:opacity-50"
                >
                  {isLoadingHistory ? 'Retrying...' : 'Retry'}
                </button>
              )}
            </div>
          ) : sessions.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[#666660]">
              No previous analyses yet.
            </div>
          ) : (
            <div className="space-y-0.5">
              {sessions.map((session) => {
                const isActive = activeSessionId === session.id;
                const isItemDeleting = deletingIds?.has(session.id);
                return (
                  <div
                    key={session.id}
                    onClick={() => onSelectSession(session.id)}
                    className={`group relative flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-xs transition-all ${
                      isActive
                        ? 'bg-[#B7D93D]/10 text-[#EDEDE9] font-medium border border-[#B7D93D]/25'
                        : 'text-[#9E9E98] hover:bg-white/5 hover:text-[#EDEDE9]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      <div className="shrink-0">
                        {getTypeIcon(session.result?.detectedType || session.selectedModel)}
                      </div>
                      <span className="truncate text-xs">
                        {session.title || 'Untitled analysis'}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {confirmingDeleteId === session.id ? (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            id={`sidebar-confirm-delete-${session.id}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteSession(session.id, e);
                              setConfirmingDeleteId(null);
                            }}
                            disabled={isItemDeleting}
                            title="Confirm delete"
                            className="text-[10px] px-1.5 py-0.5 rounded bg-red-950/70 border border-red-800/60 text-red-300 hover:bg-red-900/60 font-mono transition-colors"
                          >
                            {isItemDeleting ? '...' : 'Delete'}
                          </button>
                          <button
                            id={`sidebar-cancel-delete-${session.id}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmingDeleteId(null);
                            }}
                            title="Cancel"
                            className="text-[10px] px-1 py-0.5 rounded bg-white/5 text-[#9E9E98] hover:bg-white/10"
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          id={`sidebar-delete-btn-${session.id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmingDeleteId(session.id);
                          }}
                          disabled={isItemDeleting}
                          title="Delete session"
                          className="text-[#666660] hover:text-red-400 p-1 rounded hover:bg-white/5 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    {isActive && (
                      <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-[#B7D93D] rounded-r" />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Bottom Profile section */}
        <div className="p-3 border-t border-white/5 relative" ref={profileMenuRef}>
          {user ? (
            <>
              {/* Profile Menu Popover */}
              {profileMenuOpen && (
                <div 
                  id="sidebar-profile-menu"
                  className="absolute bottom-16 left-3 right-3 bg-[#161715] border border-white/10 rounded-xl p-1.5 shadow-xl z-50 animate-in fade-in slide-in-from-bottom-2 duration-150"
                >
                  <div className="px-2.5 py-2 border-b border-white/5 mb-1">
                    <div className="text-xs font-medium text-[#EDEDE9]">{user.name}</div>
                    <div className="text-[11px] text-[#666660] truncate">{user.email}</div>
                  </div>

                  <button
                    id="profile-menu-settings"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      onOpenSettings();
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-[#9E9E98] hover:text-[#EDEDE9] hover:bg-white/5 transition-colors"
                  >
                    <Settings className="w-3.5 h-3.5" />
                    <span>Account settings</span>
                  </button>

                  <button
                    id="profile-menu-signout"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      onSignOut();
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-red-400 hover:bg-red-950/30 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign out</span>
                  </button>
                </div>
              )}

              {/* Profile pill trigger */}
              <button
                id="sidebar-profile-btn"
                onClick={() => setProfileMenuOpen(!profileMenuOpen)}
                className="w-full flex items-center justify-between p-2 rounded-xl hover:bg-white/5 text-left transition-colors"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-lg bg-[#1C1E1A] border border-white/10 flex items-center justify-center text-xs font-medium text-[#B7D93D]">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-[#EDEDE9] truncate leading-tight">
                      {user.name}
                    </div>
                    <div className="text-[10px] text-[#666660] truncate">
                      {user.role || 'Google Account'}
                    </div>
                  </div>
                </div>
                <MoreVertical className="w-3.5 h-3.5 text-[#666660]" />
              </button>
            </>
          ) : (
            /* GUEST MODE: Clear indication with optional Sign In button, NO logout or account controls */
            <div className="p-2 rounded-xl bg-[#161715]/60 border border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-2 h-2 rounded-full bg-[#9E9E98]" />
                <span className="text-xs text-[#9E9E98] font-medium">Guest Mode</span>
              </div>
              {onSignIn && (
                <button
                  id="sidebar-guest-signin-btn"
                  onClick={onSignIn}
                  className="text-xs text-[#B7D93D] hover:underline font-medium px-1 py-0.5"
                >
                  Sign In
                </button>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
