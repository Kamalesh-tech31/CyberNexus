import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  AlertTriangle, 
  CheckCircle2, 
  ShieldAlert, 
  ShieldCheck, 
  Info, 
  ExternalLink,
  Cpu,
  BarChart2,
  Sliders,
  Layers,
  Copy,
  Check,
  Zap,
  Lock,
  QrCode,
  BrainCircuit
} from 'lucide-react';
import { AnalysisResult } from '../types';
import { TechnicalDetailsModal } from './TechnicalDetailsModal';

interface AnalysisResultViewProps {
  result: AnalysisResult;
}

export const AnalysisResultView: React.FC<AnalysisResultViewProps> = ({ result }) => {
  const [isDetailedOpen, setIsDetailedOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isTechModalOpen, setIsTechModalOpen] = useState(false);

  const isSafe = result.severity === 'safe';

  const getVerdictStyle = () => {
    if (isSafe) {
      return {
        bg: 'bg-emerald-950/20 border-emerald-800/30',
        badge: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
        text: 'text-emerald-400',
        icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />
      };
    }
    if (result.severity === 'critical' || result.severity === 'high') {
      return {
        bg: 'bg-rose-950/20 border-rose-800/30',
        badge: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
        text: 'text-rose-400',
        icon: <ShieldAlert className="w-5 h-5 text-rose-400" />
      };
    }
    return {
      bg: 'bg-amber-950/20 border-amber-800/30',
      badge: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
      text: 'text-amber-400',
      icon: <AlertTriangle className="w-5 h-5 text-amber-400" />
    };
  };

  const style = getVerdictStyle();

  const handleCopyReport = () => {
    const report = `CyberNexus ML Report:
Verdict: ${result.verdict} (${result.confidence}% confidence)
Type: ${result.detectedType.toUpperCase()}
Summary: ${result.summary}
Recommended Action: ${result.recommendedAction}`;
    navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div id="analysis-result-view" className="w-full bg-[#10110F] border border-white/5 rounded-2xl p-6 sm:p-7 shadow-sm space-y-6">
      {/* Top Banner: Primary Layer */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-white/5">
        <div className="flex items-start sm:items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-[#161715] border border-white/5 shrink-0">
            {style.icon}
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap mb-1">
              <h2 className="text-xl sm:text-2xl font-medium tracking-tight text-[#EDEDE9]">
                {result.verdict}
              </h2>
              <span className={`text-xs font-mono font-medium px-2.5 py-0.5 rounded-full ${style.badge}`}>
                {Number(result.confidence).toFixed(1)}% confidence
              </span>
            </div>
            <p className="text-xs text-[#9E9E98] font-normal">
              Classified via {result.modelMetrics.modelName} · {result.analyzedAt}
            </p>
            <p className="text-[10px] text-[#555550] mt-0.5 italic">
              Confidence reflects predicted probability, not certainty.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center">
          {result.technicalDetails && (
            <button
              onClick={() => setIsTechModalOpen(true)}
              title="View model-grounded technical details"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-[#B7D93D]/10 border border-white/5 hover:border-[#B7D93D]/30 text-xs text-[#9E9E98] hover:text-[#B7D93D] transition-colors"
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              <span>Technical details</span>
            </button>
          )}
          <button
            onClick={handleCopyReport}
            title="Copy analysis summary"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-[#9E9E98] hover:text-[#EDEDE9] transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#B7D93D]" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Share'}</span>
          </button>
        </div>
      </div>

      {/* Extracted QR Payload display if applicable */}
      {result.extractedContent?.qrDecodedPayload && (
        <div className="p-4 rounded-xl bg-[#161715] border border-white/5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium text-[#9E9E98]">
            <QrCode className="w-3.5 h-3.5 text-[#B7D93D]" />
            <span>Extracted QR Matrix Payload</span>
          </div>
          <div className="font-mono text-xs text-[#EDEDE9] bg-black/40 p-2.5 rounded-lg break-all border border-white/5">
            {result.extractedContent.qrDecodedPayload}
          </div>
        </div>
      )}

      {/* Summary Narrative */}
      <div className="text-sm text-[#EDEDE9] leading-relaxed">
        {result.summary}
      </div>

      {/* Why we flagged this */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-medium uppercase tracking-wider text-[#9E9E98]">
          {isSafe ? 'Key Trust Factors' : 'Why we flagged this'}
        </h4>
        <ul className="space-y-2">
          {result.reasons.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-2.5 text-xs sm:text-sm text-[#EDEDE9]/90 leading-relaxed">
              <span className="w-1.5 h-1.5 rounded-full bg-[#B7D93D] mt-2 shrink-0" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Recommended Action */}
      <div className="p-4 rounded-xl bg-[#161715] border border-white/5 space-y-1.5">
        <h4 className="text-xs font-medium uppercase tracking-wider text-[#9E9E98]">
          Recommended action
        </h4>
        <p className="text-xs sm:text-sm font-medium text-[#EDEDE9] leading-relaxed">
          {result.recommendedAction}
        </p>
      </div>

      {/* Progressive Disclosure Toggle */}
      <div className="pt-2">
        <button
          id="toggle-detailed-analysis-btn"
          onClick={() => setIsDetailedOpen(!isDetailedOpen)}
          className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-xs sm:text-sm text-[#EDEDE9] border border-white/5 transition-all group"
        >
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-[#B7D93D]" />
            <span className="font-medium">
              {isDetailedOpen ? 'Hide detailed ML analysis' : 'View detailed ML analysis'}
            </span>
          </div>
          {isDetailedOpen ? (
            <ChevronUp className="w-4 h-4 text-[#9E9E98] group-hover:text-[#EDEDE9]" />
          ) : (
            <ChevronDown className="w-4 h-4 text-[#9E9E98] group-hover:text-[#EDEDE9]" />
          )}
        </button>
      </div>

      {/* DETAILED ML ANALYSIS SECTION (EXPANDABLE) */}
      {isDetailedOpen && (
        <div 
          id="detailed-ml-analysis-section"
          className="pt-4 border-t border-white/5 space-y-6 animate-in fade-in slide-in-from-top-2 duration-200"
        >
          {/* Section 1: Model Analysis Summary Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-xl bg-[#161715] border border-white/5">
              <div className="text-[11px] text-[#9E9E98] uppercase tracking-wider font-mono mb-1">
                Analysis Type
              </div>
              <div className="text-sm font-medium text-[#EDEDE9] uppercase">
                {result.detectedType} Pipeline
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#161715] border border-white/5">
              <div className="text-[11px] text-[#9E9E98] uppercase tracking-wider font-mono mb-1">
                Target Prediction
              </div>
              <div className={`text-sm font-medium ${style.text}`}>
                {result.verdict}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#161715] border border-white/5">
              <div className="text-[11px] text-[#9E9E98] uppercase tracking-wider font-mono mb-1">
                Model Confidence
              </div>
              <div className="text-sm font-mono font-medium text-[#B7D93D]">
                {Number(result.confidence).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Section 2: Detected Indicators */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-medium uppercase tracking-wider text-[#9E9E98]">
                Detected Feature Indicators
              </h4>
              <span className="text-[11px] text-[#666660]">
                {result.indicators.length} vectors analyzed
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {result.indicators.map((ind) => {
                const isIndSafe = ind.severity === 'safe';
                return (
                  <div
                    key={ind.id}
                    className="p-3 rounded-xl bg-[#161715] border border-white/5 hover:border-white/10 transition-colors flex flex-col justify-between gap-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-[#666660] mb-0.5">
                          {ind.category}
                        </div>
                        <div className="text-xs font-medium text-[#EDEDE9]">
                          {ind.name}
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-md ${
                          isIndSafe
                            ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/30'
                            : 'bg-rose-950/40 text-rose-400 border border-rose-800/30'
                        }`}
                      >
                        {ind.severity.toUpperCase()}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#9E9E98] leading-relaxed">
                      {ind.description}
                    </p>

                    {ind.metricValue && (
                      <div className="pt-1.5 border-t border-white/5 text-[10px] font-mono text-[#B7D93D] flex items-center justify-between">
                        <span>Metric reading</span>
                        <span>{ind.metricValue}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 3: Model Explanation (LIME / SHAP Synthesized) */}
          <div className="p-4 rounded-xl bg-[#161715] border border-white/5 space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-[#EDEDE9]">
              <Cpu className="w-3.5 h-3.5 text-[#B7D93D]" />
              <span>Model Rationale & Explainability</span>
            </div>
            <p className="text-xs text-[#9E9E98] leading-relaxed">
              {result.explanation}
            </p>
          </div>

          {/* Section 4: Model Information & Academic Benchmark Metrics */}
          <div className="p-4 rounded-xl bg-[#161715] border border-white/5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BarChart2 className="w-3.5 h-3.5 text-[#B7D93D]" />
                <span className="text-xs font-medium text-[#EDEDE9]">
                  Model Architecture & Evaluation Metrics
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#666660]">
                Model Details
              </span>
            </div>

            {/* Model Spec List */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-[#666660] block text-[11px]">Model Engine:</span>
                <span className="text-[#EDEDE9] font-medium font-mono text-xs">{result.modelMetrics.modelName}</span>
              </div>
              <div>
                <span className="text-[#666660] block text-[11px]">Architecture:</span>
                <span className="text-[#EDEDE9] font-medium text-xs">{result.modelMetrics.architecture}</span>
              </div>
              <div>
                <span className="text-[#666660] block text-[11px]">Training Corpus:</span>
                <span className="text-[#EDEDE9] font-medium text-xs">{result.modelMetrics.datasetName}</span>
              </div>
              {result.modelMetrics.inferenceLatency && (
                <div>
                  <span className="text-[#666660] block text-[11px]">Inference Latency:</span>
                  <span className="text-[#B7D93D] font-mono font-medium text-xs">{result.modelMetrics.inferenceLatency}</span>
                </div>
              )}
            </div>

            {/* Metrics Score Cards — only shown if backend provides benchmark data */}
            {(result.modelMetrics.accuracy != null || result.modelMetrics.precision != null || result.modelMetrics.recall != null || result.modelMetrics.f1Score != null) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
              <div className="bg-[#10110F] p-2.5 rounded-lg text-center border border-white/5">
                <div className="text-[10px] font-mono text-[#666660] uppercase">Accuracy</div>
                <div className="text-sm font-mono font-semibold text-[#EDEDE9] mt-0.5">
                  {result.modelMetrics.accuracy != null ? `${result.modelMetrics.accuracy}%` : 'N/A'}
                </div>
              </div>
              <div className="bg-[#10110F] p-2.5 rounded-lg text-center border border-white/5">
                <div className="text-[10px] font-mono text-[#666660] uppercase">Precision</div>
                <div className="text-sm font-mono font-semibold text-[#EDEDE9] mt-0.5">
                  {result.modelMetrics.precision != null ? `${result.modelMetrics.precision}%` : 'N/A'}
                </div>
              </div>
              <div className="bg-[#10110F] p-2.5 rounded-lg text-center border border-white/5">
                <div className="text-[10px] font-mono text-[#666660] uppercase">Recall</div>
                <div className="text-sm font-mono font-semibold text-[#EDEDE9] mt-0.5">
                  {result.modelMetrics.recall != null ? `${result.modelMetrics.recall}%` : 'N/A'}
                </div>
              </div>
              <div className="bg-[#10110F] p-2.5 rounded-lg text-center border border-white/5">
                <div className="text-[10px] font-mono text-[#666660] uppercase">F1 Score</div>
                <div className="text-sm font-mono font-semibold text-[#B7D93D] mt-0.5">
                  {result.modelMetrics.f1Score != null ? `${result.modelMetrics.f1Score}%` : 'N/A'}
                </div>
              </div>
            </div>
            )}

            {/* Feature Importance Weights Bar Chart */}
            <div className="pt-2 space-y-2">
              <div className="text-[11px] text-[#9E9E98] uppercase font-mono tracking-wider">
                Top Feature Weights (Attribution)
              </div>
              <div className="space-y-2">
                {result.modelMetrics.featureWeights.map((fw, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-[#EDEDE9]">
                      <span className="text-[#9E9E98]">{fw.feature}</span>
                      <span className="font-mono text-[#B7D93D]">{(fw.weight * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-[#10110F] rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-[#B7D93D] rounded-full transition-all duration-500" 
                        style={{ width: `${fw.weight * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tier 3: Technical Details Modal */}
      {result.technicalDetails && (
        <TechnicalDetailsModal
          isOpen={isTechModalOpen}
          onClose={() => setIsTechModalOpen(false)}
          details={result.technicalDetails}
        />
      )}
    </div>
  );
};
