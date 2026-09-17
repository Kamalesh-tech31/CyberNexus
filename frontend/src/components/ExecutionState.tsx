import React from 'react';
import { Check, Loader2, Sparkles, Circle } from 'lucide-react';
import { ExecutionStage } from '../types';

interface ExecutionStateProps {
  stages: ExecutionStage[];
  currentStageIndex: number;
  detectedType?: string;
  onSkip?: () => void;
}

export const ExecutionState: React.FC<ExecutionStateProps> = ({
  stages,
  currentStageIndex,
  detectedType,
  onSkip,
}) => {
  return (
    <div id="execution-state" className="w-full bg-[#10110F] border border-white/5 rounded-2xl p-6 sm:p-7 max-w-2xl mx-auto shadow-sm my-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-[#B7D93D] animate-pulse" />
          <h3 className="text-sm sm:text-base font-medium text-[#EDEDE9] tracking-tight">
            Analyzing your input
          </h3>
        </div>
        {detectedType && (
          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-[#161715] text-[#B7D93D] border border-[#B7D93D]/20">
            Detected: {detectedType}
          </span>
        )}
      </div>

      {/* Progressive Stage List */}
      <div className="space-y-3.5 relative pl-1">
        {stages.map((stage, idx) => {
          const isDone = idx < currentStageIndex;
          const isCurrent = idx === currentStageIndex;
          const isPending = idx > currentStageIndex;

          return (
            <div
              key={stage.id || idx}
              className={`flex items-center gap-3 text-xs sm:text-sm transition-all duration-200 ${
                isDone
                  ? 'text-[#9E9E98]'
                  : isCurrent
                  ? 'text-[#EDEDE9] font-medium'
                  : 'text-[#666660]'
              }`}
            >
              {/* Stage Icon */}
              <div className="w-5 h-5 flex items-center justify-center shrink-0">
                {isDone ? (
                  <div className="w-4 h-4 rounded-full bg-[#B7D93D]/20 text-[#B7D93D] flex items-center justify-center">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                ) : isCurrent ? (
                  <div className="relative flex items-center justify-center">
                    <div className="w-3.5 h-3.5 rounded-full border-2 border-[#B7D93D] border-t-transparent animate-spin" />
                  </div>
                ) : (
                  <div className="w-2 h-2 rounded-full bg-white/10" />
                )}
              </div>

              {/* Stage Label */}
              <div className="flex items-center justify-between flex-1 min-w-0">
                <span className="truncate">{stage.label}</span>
                {isCurrent && (
                  <span className="text-[10px] text-[#B7D93D] font-mono tracking-wider animate-pulse">
                    PROCESSING...
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Subtext info */}
      <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between text-[11px] text-[#666660]">
        <span>Multi-layer feature vector extraction</span>
        {onSkip && (
          <button
            onClick={onSkip}
            className="text-[#9E9E98] hover:text-[#EDEDE9] underline transition-colors cursor-pointer"
          >
            Show result instantly
          </button>
        )}
      </div>
    </div>
  );
};
