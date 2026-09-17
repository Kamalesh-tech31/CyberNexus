import React, { useState, useEffect, useRef } from 'react';
import { X, Sliders, Database, Shield, Cpu, Check, RefreshCw, AlertTriangle, AlertCircle } from 'lucide-react';
import { UserProfile } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile;
  onUpdateUser: (user: UserProfile) => void;
  onDeleteAccount?: () => Promise<void>;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  user,
  onUpdateUser,
  onDeleteAccount,
}) => {
  const [name, setName] = useState(user.name);
  const [sensitivity, setSensitivity] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [autoDetectThreshold, setAutoDetectThreshold] = useState(85);
  const [isSaved, setIsSaved] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  if (!isOpen) return null;

  const handleClose = () => {
    setIsConfirmingDelete(false);
    setDeleteError(null);
    onClose();
  };

  const handleDelete = async () => {
    if (!onDeleteAccount || isDeletingAccount) return;
    setIsDeletingAccount(true);
    setDeleteError(null);
    try {
      await onDeleteAccount();
    } catch (err: any) {
      if (isMountedRef.current) {
        setDeleteError(err?.message || 'Account deletion failed. Please try again.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsDeletingAccount(false);
      }
    }
  };

  const handleSave = () => {
    onUpdateUser({ ...user, name });
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        id="settings-modal"
        className="w-full max-w-lg bg-[#10110F] border border-white/10 rounded-2xl p-6 sm:p-7 shadow-2xl relative space-y-6"
      >
        {/* Close Button */}
        <button
          onClick={handleClose}
          className="absolute top-5 right-5 text-[#9E9E98] hover:text-[#EDEDE9] p-1.5 rounded-lg hover:bg-white/5 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-[#161715] border border-white/5">
            <Sliders className="w-5 h-5 text-[#B7D93D]" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-[#EDEDE9] tracking-tight">
              Settings & ML Preferences
            </h3>
            <p className="text-xs text-[#9E9E98]">
              Configure model sensitivity and user preferences.
            </p>
          </div>
        </div>

        {/* Profile Settings */}
        <div className="space-y-3">
          <label className="block text-xs font-mono uppercase tracking-wider text-[#666660]">
            User Profile
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <span className="text-[11px] text-[#9E9E98] block mb-1">Display Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[#161715] border border-white/10 rounded-xl px-3 py-2 text-xs text-[#EDEDE9] focus:outline-none focus:border-[#B7D93D]/50"
              />
            </div>
            <div>
              <span className="text-[11px] text-[#9E9E98] block mb-1">Email Account</span>
              <input
                type="email"
                disabled
                value={user.email}
                className="w-full bg-[#161715]/50 border border-white/5 rounded-xl px-3 py-2 text-xs text-[#666660] cursor-not-allowed"
              />
            </div>
          </div>
        </div>

        {/* ML Sensitivity Settings */}
        <div className="space-y-3 pt-3 border-t border-white/5">
          <label className="block text-xs font-mono uppercase tracking-wider text-[#666660]">
            Threat Classification Sensitivity
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(['conservative', 'balanced', 'aggressive'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSensitivity(s)}
                className={`p-3 rounded-xl border text-xs font-medium capitalize transition-all text-center ${
                  sensitivity === s
                    ? 'bg-[#B7D93D]/10 border-[#B7D93D]/40 text-[#EDEDE9]'
                    : 'bg-[#161715] border-white/5 text-[#9E9E98] hover:border-white/10'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-[#666660]">
            Balanced mode uses optimal F1 score threshold (0.50). Aggressive minimizes false negatives for high-security environments.
          </p>
        </div>

        {/* Supabase Architecture Status */}
        <div className="p-3.5 rounded-xl bg-[#161715] border border-white/5 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2.5">
            <Database className="w-4 h-4 text-[#9E9E98]" />
            <div>
              <div className="font-medium text-[#EDEDE9]">Supabase Production Schema</div>
              <div className="text-[11px] text-[#666660]">PostgreSQL Row Level Security & persistent history active</div>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-md bg-emerald-950/40 text-emerald-400 border border-emerald-800/30 text-[10px] font-mono">
            ACTIVE
          </span>
        </div>

        {/* Danger Zone: Account Deletion */}
        {onDeleteAccount && (
          <div className="p-4 rounded-xl bg-red-950/20 border border-red-900/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-red-400 text-xs font-medium">
                <AlertTriangle className="w-4 h-4" />
                <span>Danger Zone</span>
              </div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-red-400/80 bg-red-950/60 px-2 py-0.5 rounded border border-red-900/40">
                Irreversible
              </span>
            </div>

            <p className="text-[11px] text-[#9E9E98] leading-relaxed">
              Permanently delete your account, Supabase authentication record, and all historical analysis sessions. This operation is fail-closed and cannot be undone.
            </p>

            {deleteError && (
              <div className="p-2.5 rounded-lg bg-red-950/50 border border-red-800/50 text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-red-400" />
                <span>{deleteError}</span>
              </div>
            )}

            {isConfirmingDelete ? (
              <div className="p-3 rounded-lg bg-[#161715] border border-red-900/40 space-y-2.5 animate-in fade-in duration-150">
                <div className="text-xs text-red-300 font-medium">
                  Are you absolutely sure you want to delete your account?
                </div>
                <p className="text-[11px] text-[#666660]">
                  All analysis messages, ML results, and user profile data will be permanently wiped.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    id="settings-confirm-delete-account-btn"
                    onClick={handleDelete}
                    disabled={isDeletingAccount}
                    className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium text-xs transition-colors flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                  >
                    {isDeletingAccount ? (
                      <>
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Deleting Account...</span>
                      </>
                    ) : (
                      <span>Yes, Permanently Delete</span>
                    )}
                  </button>
                  <button
                    id="settings-cancel-delete-account-btn"
                    onClick={() => setIsConfirmingDelete(false)}
                    disabled={isDeletingAccount}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-[#9E9E98] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                id="settings-delete-account-btn"
                onClick={() => setIsConfirmingDelete(true)}
                className="px-3 py-1.5 rounded-lg bg-red-950/40 hover:bg-red-900/40 text-red-400 hover:text-red-300 border border-red-900/40 text-xs font-medium transition-colors cursor-pointer"
              >
                Delete Account
              </button>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-xs text-[#9E9E98] hover:text-[#EDEDE9] hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 rounded-xl bg-[#B7D93D] text-[#0B0C0A] hover:bg-[#C6E74B] font-medium text-xs transition-colors flex items-center gap-1.5"
          >
            {isSaved ? <Check className="w-3.5 h-3.5" /> : null}
            <span>{isSaved ? 'Saved' : 'Save Changes'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
