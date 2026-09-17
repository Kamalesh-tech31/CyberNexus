import React, { useEffect, useRef } from 'react';
import { X, ChevronUp, ChevronDown, BrainCircuit, SlidersHorizontal, Type } from 'lucide-react';
import { TechnicalDetails, StructuralSignal, TextSignal } from '../types';

interface TechnicalDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  details: TechnicalDetails;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function ContributionBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(Math.abs(value) / max, 1) * 100 : 0;
  const isRisk = value > 0;
  return (
    <div className="flex items-center gap-2 min-w-0 flex-1">
      <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isRisk ? 'bg-rose-400/70' : 'bg-emerald-400/50'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-[10px] font-mono shrink-0 w-14 text-right ${isRisk ? 'text-rose-400' : 'text-emerald-400'}`}>
        {value > 0 ? '+' : ''}{value.toFixed(4)}
      </span>
    </div>
  );
}

function SectionHeader({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <div className="text-[#B7D93D]">{icon}</div>
      <span className="text-xs font-medium uppercase tracking-wider text-[#9E9E98]">{label}</span>
    </div>
  );
}

function StructuralSignalRow({ sig, maxContrib }: { sig: StructuralSignal; maxContrib: number; key?: React.Key }) {
  const isRisk = sig.direction === 'increases_risk';
  return (
    <div className="py-2.5 border-b border-white/5 last:border-0">
      <div className="flex items-start justify-between gap-3 mb-1.5">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-[#EDEDE9] font-medium">{sig.feature_label}</span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${isRisk ? 'bg-rose-950/60 text-rose-400 border border-rose-800/30' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/30'}`}>
              {isRisk ? '↑ risk' : '↓ risk'}
            </span>
          </div>
          <div className="text-[10px] text-[#666660] mt-0.5 leading-snug">{sig.description}</div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-[11px] font-mono text-[#B7D93D]">{sig.raw_value_display}</div>
          <div className="text-[9px] text-[#555550]">{sig.feature}</div>
        </div>
      </div>
      <ContributionBar value={sig.contribution} max={maxContrib} />
    </div>
  );
}

function TextSignalRow({ sig, maxContrib }: { sig: TextSignal; maxContrib: number; key?: React.Key }) {
  const isRisk = sig.direction === 'increases_risk';
  return (
    <div className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
      <code className="text-[11px] text-[#EDEDE9] font-mono min-w-[90px] shrink-0 truncate">{sig.token}</code>
      <ContributionBar value={sig.contribution} max={maxContrib} />
      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded shrink-0 ${isRisk ? 'bg-rose-950/60 text-rose-400 border border-rose-800/30' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/30'}`}>
        {isRisk ? '↑' : '↓'}
      </span>
    </div>
  );
}

// ── Main Modal ─────────────────────────────────────────────────────────────

export const TechnicalDetailsModal: React.FC<TechnicalDetailsModalProps> = ({ isOpen, onClose, details }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Keyboard & backdrop close
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const { structural_signals, text_signals, model_metadata, channel, calibrated_confidence, operational_threshold, raw_score } = details;

  // Compute max contribution magnitude for bar scaling
  const allContribs = structural_signals.map(s => Math.abs(s.contribution));
  if (text_signals) {
    const allTextSigs = [
      ...(text_signals.tokens ?? []),
      ...(text_signals.subject ?? []),
      ...(text_signals.body ?? []),
    ];
    allTextSigs.forEach(s => allContribs.push(Math.abs(s.contribution)));
  }
  const maxContrib = allContribs.length > 0 ? Math.max(...allContribs) : 1;

  const metaFields: { label: string; value: string }[] = [
    { label: 'Channel', value: model_metadata.channel },
    { label: 'Model', value: model_metadata.model_name },
    { label: 'Architecture', value: model_metadata.architecture },
    { label: 'Calibration', value: model_metadata.calibration },
    { label: 'Version', value: model_metadata.model_version },
    { label: 'Trained on', value: model_metadata.trained_on },
  ].filter(f => f.value && f.value.length > 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      aria-modal="true"
      role="dialog"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Modal panel */}
      <div
        ref={modalRef}
        className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-[#10110F] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-[#161715] border border-white/5">
              <BrainCircuit className="w-4 h-4 text-[#B7D93D]" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-[#EDEDE9]">Technical Details</h3>
              <p className="text-[11px] text-[#666660] font-mono mt-0.5">
                {model_metadata.channel} · {model_metadata.model_name} · Calibrated confidence {calibrated_confidence.toFixed(1)}%
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#666660] hover:text-[#EDEDE9] hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">

          {/* ── Confidence metrics summary ── */}
          <div className="grid grid-cols-3 gap-2">
            <div className="p-3 rounded-xl bg-[#161715] border border-white/5 text-center">
              <div className="text-[10px] text-[#666660] font-mono uppercase mb-1">Raw Score</div>
              <div className="text-sm font-mono font-semibold text-[#EDEDE9]">{(raw_score * 100).toFixed(1)}%</div>
            </div>
            <div className="p-3 rounded-xl bg-[#161715] border border-white/5 text-center">
              <div className="text-[10px] text-[#666660] font-mono uppercase mb-1">Calibrated</div>
              <div className="text-sm font-mono font-semibold text-[#B7D93D]">{calibrated_confidence.toFixed(1)}%</div>
            </div>
            <div className="p-3 rounded-xl bg-[#161715] border border-white/5 text-center">
              <div className="text-[10px] text-[#666660] font-mono uppercase mb-1">Threshold</div>
              <div className="text-sm font-mono font-semibold text-[#EDEDE9]">{(operational_threshold * 100).toFixed(1)}%</div>
            </div>
          </div>

          {/* ── Structural Signals ── */}
          <div className="p-4 rounded-xl bg-[#161715] border border-white/5">
            <SectionHeader icon={<SlidersHorizontal className="w-3.5 h-3.5" />} label="Structural Feature Contributions" />
            <div>
              {structural_signals.map(sig => (
                <StructuralSignalRow key={sig.feature} sig={sig} maxContrib={maxContrib} />
              ))}
            </div>
          </div>

          {/* ── Text Signals (SMS: flat, Email: subject/body grouped, URL: omitted entirely) ── */}
          {channel === 'sms' && text_signals?.tokens && text_signals.tokens.length > 0 && (
            <div className="p-4 rounded-xl bg-[#161715] border border-white/5">
              <SectionHeader icon={<Type className="w-3.5 h-3.5" />} label="Token Contributions (TF-IDF)" />
              <div>
                {text_signals.tokens.map((sig, idx) => (
                  <TextSignalRow key={`tok-${idx}`} sig={sig} maxContrib={maxContrib} />
                ))}
              </div>
            </div>
          )}

          {channel === 'email' && text_signals && (
            <>
              {text_signals.subject && text_signals.subject.length > 0 && (
                <div className="p-4 rounded-xl bg-[#161715] border border-white/5">
                  <SectionHeader icon={<Type className="w-3.5 h-3.5" />} label="Subject Token Contributions" />
                  <div>
                    {text_signals.subject.map((sig, idx) => (
                      <TextSignalRow key={`subj-${idx}`} sig={sig} maxContrib={maxContrib} />
                    ))}
                  </div>
                </div>
              )}
              {text_signals.body && text_signals.body.length > 0 && (
                <div className="p-4 rounded-xl bg-[#161715] border border-white/5">
                  <SectionHeader icon={<Type className="w-3.5 h-3.5" />} label="Body Token Contributions" />
                  <div>
                    {text_signals.body.map((sig, idx) => (
                      <TextSignalRow key={`body-${idx}`} sig={sig} maxContrib={maxContrib} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {/* URL: text_signals is null — nothing rendered here (intended) */}

          {/* ── Model Metadata ── */}
          <div className="p-4 rounded-xl bg-[#161715] border border-white/5">
            <SectionHeader icon={<BrainCircuit className="w-3.5 h-3.5" />} label="Model Metadata" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2.5 gap-x-4">
              {metaFields.map(f => (
                <div key={f.label}>
                  <div className="text-[10px] text-[#666660] uppercase font-mono">{f.label}</div>
                  <div className="text-[11px] text-[#EDEDE9] font-medium leading-snug mt-0.5">{f.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer disclaimer */}
        <div className="px-5 py-3 border-t border-white/5 shrink-0">
          <p className="text-[10px] text-[#555550] leading-relaxed text-center">
            Confidence reflects predicted probability, not certainty. Feature contributions describe model behavior and do not prove intent.
          </p>
        </div>
      </div>
    </div>
  );
};
