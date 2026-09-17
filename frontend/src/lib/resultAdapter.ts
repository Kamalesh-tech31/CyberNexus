/**
 * CyberNexus - API Response to UI Result Adapter
 * Phase 6E: Transforms real Phase 6D API response into frontend AnalysisResult and TechnicalDetails.
 */

import { AnalysisResult, AnalysisType, DetectedIndicator, TechnicalDetails, ThreatSeverity, VerdictType } from '../types';
import { AnalysisApiResponse } from './api';

const STRUCTURAL_FEATURE_NAMES: Record<string, string> = {
  // SMS
  message_length: 'Message Length',
  digit_to_length_ratio: 'Digit To Length Ratio',
  url_presence: 'URL Presence',
  punctuation_density: 'Punctuation Density',
  special_char_count: 'Special Char Count',
  uppercase_ratio: 'Uppercase Ratio',
  // Email
  email_length: 'Email Length',
  url_count: 'URL Count',
  digit_count: 'Digit Count',
  exclamation_count: 'Exclamation Count',
  all_caps_word_count: 'All Caps Word Count',
  urgency_keyword_count: 'Urgency Keyword Count',
  // URL
  hostname_length: 'Hostname Length',
  path_length: 'Path Length',
  query_length: 'Query Length',
  dot_count: 'Dot Count',
  hyphen_count: 'Hyphen Count',
  suspicious_token_presence: 'Suspicious Token Presence',
  subdomain_depth: 'Subdomain Depth',
  ip_hostname: 'IP Hostname',
  https_presence: 'HTTPS Presence',
  at_symbol_presence: 'At Symbol Presence',
  embedded_double_slash_count: 'Embedded Double Slash Count',
};

export function adaptApiResponseToResult(
  apiResp: AnalysisApiResponse,
  submittedInput: string,
  sessionId: string
): AnalysisResult {
  const isSafe = apiResp.prediction.includes('Safe') || apiResp.prediction.includes('Non-URL');
  const severity: ThreatSeverity = isSafe
    ? 'safe'
    : apiResp.risk_score >= 85
    ? 'critical'
    : apiResp.risk_score >= 50
    ? 'high'
    : 'medium';

  // Map Tier 2 flags into DetectedIndicator array
  const indicators: DetectedIndicator[] = apiResp.tier2?.flags
    ? apiResp.tier2.flags.map((flag, idx) => {
        const isFlagSafe = flag.status === 'false' || flag.status === 'safe';
        return {
          id: `ind-${idx + 1}`,
          category:
            apiResp.resolved_channel === 'url'
              ? 'URL'
              : apiResp.resolved_channel === 'email'
              ? 'Header'
              : apiResp.resolved_channel === 'qr'
              ? 'QR Code'
              : 'Text',
          name: flag.label,
          severity: isFlagSafe ? 'safe' : 'high',
          description: flag.detail,
        };
      })
    : (apiResp.indicators || []).map((ind, idx) => ({
        id: `ind-${idx + 1}`,
        category: 'QR Code',
        name: ind,
        severity: isSafe ? 'safe' : 'medium',
        description: ind,
      }));

  // Map Tier 3 structural contributions into TechnicalDetails format if available
  const structuralSignals = apiResp.tier3?.feature_contributions
    ? apiResp.tier3.feature_contributions.map((fc) => {
        const label =
          STRUCTURAL_FEATURE_NAMES[fc.feature] ||
          fc.feature.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        return {
          feature: fc.feature,
          feature_label: label,
          value: fc.value,
          raw_value_display:
            fc.feature.includes('presence') || fc.feature.includes('ip_hostname')
              ? fc.value === 1
                ? 'true'
                : 'false'
              : fc.value % 1 !== 0
              ? fc.value.toFixed(4)
              : String(fc.value),
          contribution: fc.contribution,
          direction: fc.direction,
          description:
            apiResp.tier2?.flags.find((f) => f.label === label)?.detail ||
            `${label} statistical factor in ML model`,
        };
      })
    : [];

  // Map text signals (preserving Email subject vs body separation)
  let textSignalsPayload: TechnicalDetails['text_signals'] = null;
  if (apiResp.resolved_channel === 'email' && apiResp.tier3?.top_text_signals) {
    const subjectSignals = apiResp.tier3.top_text_signals
      .filter((ts) => ts.source === 'subject')
      .map((ts) => ({
        token: ts.token,
        weight: ts.weight,
        contribution: ts.weight,
        direction: 'increases_risk' as const,
        origin: 'subject' as const,
      }));
    const bodySignals = apiResp.tier3.top_text_signals
      .filter((ts) => ts.source === 'body')
      .map((ts) => ({
        token: ts.token,
        weight: ts.weight,
        contribution: ts.weight,
        direction: 'increases_risk' as const,
        origin: 'body' as const,
      }));
    textSignalsPayload = {
      subject: subjectSignals,
      body: bodySignals,
    };
  } else if (apiResp.resolved_channel === 'sms' && apiResp.tier3?.top_text_signals) {
    textSignalsPayload = {
      tokens: apiResp.tier3.top_text_signals.map((ts) => ({
        token: ts.token,
        weight: ts.weight,
        contribution: ts.weight,
        direction: 'increases_risk' as const,
        origin: null,
      })),
    };
  } else {
    // URL and QR have no text signals (null)
    textSignalsPayload = null;
  }

  // Grounded Model Metadata
  const isUrlModel = apiResp.resolved_channel === 'url' || (apiResp.resolved_channel === 'qr' && apiResp.tier3);
  const modelMetadata = apiResp.tier3
    ? {
        channel: apiResp.resolved_channel.toUpperCase(),
        model_name: apiResp.tier3.model_metadata.model_name || (isUrlModel ? 'LightGBM' : 'Logistic Regression'),
        architecture: apiResp.tier3.model_metadata.architecture || (isUrlModel
          ? 'Gradient Boosted Decision Tree (n_est=200, lr=0.1, leaves=63)'
          : apiResp.resolved_channel === 'sms'
          ? "L2-regularized linear model (C=5.0, class_weight='balanced')"
          : 'L2-regularized linear model (C=10.0, class_weight=None)'),
        calibration: apiResp.tier3.model_metadata.calibration || 'Sigmoid / Platt Scaling (CalibratedClassifierCV)',
        model_version: apiResp.tier3.model_metadata.model_version,
        trained_on: apiResp.tier3.model_metadata.trained_on,
        operational_threshold: apiResp.tier3.model_metadata.operational_threshold ?? (isUrlModel ? 0.2526 : 0.5),
        note: apiResp.tier3.model_metadata.note,
      }
    : {
        channel: 'QR',
        model_name: 'QR Optical Decoder',
        architecture: 'zxing-cpp optical barcode engine',
        calibration: 'N/A (Deterministic Parser)',
        model_version: 'v1.0-qr-resolver',
        trained_on: 'QR Code Specification (ISO/IEC 18004)',
        operational_threshold: 0,
        note: 'Decoded QR payload without URL classification.',
      };

  const technicalDetails: TechnicalDetails | undefined = apiResp.tier3
    ? {
        channel: apiResp.resolved_channel,
        predicted_class: isSafe ? 0 : 1,
        predicted_label: apiResp.prediction,
        raw_score: apiResp.confidence,
        calibrated_confidence: apiResp.confidence * 100, // Exact calibrated probability percentage
        operational_threshold: modelMetadata.operational_threshold,
        structural_signals: structuralSignals,
        text_signals: textSignalsPayload,
        model_metadata: modelMetadata,
      }
    : undefined;

  // Construct UI ModelMetrics from real response — no fabricated benchmark numbers
  const modelMetrics = {
    modelName: modelMetadata.model_name,
    architecture: modelMetadata.architecture,
    accuracy: null,
    precision: null,
    recall: null,
    f1Score: null,
    inferenceLatency: null,
    datasetName: modelMetadata.trained_on,
    samplesTrained: null,
    featureWeights: structuralSignals.slice(0, 5).map((s) => ({
      feature: s.feature_label,
      weight: Math.min(Math.abs(s.contribution) / 5.0, 1.0),
    })),
  };

  const summary = apiResp.tier1?.summary || (apiResp.reasons?.[0] ?? apiResp.prediction);
  const explanation = apiResp.tier1?.summary
    ? `${apiResp.tier1.summary} ${apiResp.reasons.length > 0 ? apiResp.reasons[0] : ''}`
    : (apiResp.reasons?.join(' ') ?? '');

  return {
    id: apiResp.analysis_id || sessionId || `res-${Date.now()}`,
    detectedType: apiResp.resolved_channel,
    verdict: apiResp.prediction as VerdictType,
    confidence: Number((apiResp.confidence * 100).toFixed(1)), // 1 decimal place format
    severity,
    summary,
    reasons: apiResp.reasons,
    recommendedAction: apiResp.recommendation,
    extractedContent:
      apiResp.resolved_channel === 'email'
        ? { messageBody: submittedInput }
        : apiResp.resolved_channel === 'url'
        ? { targetUrl: submittedInput }
        : apiResp.resolved_channel === 'qr'
        ? {
            qrDecodedPayload: apiResp.qr_decoded_payload || (apiResp.qr_payloads?.join(', ')),
            qrPayloadType: apiResp.qr_payload_type,
            targetUrl: apiResp.qr_delegated_url,
          }
        : undefined,
    indicators,
    explanation,
    modelMetrics,
    analyzedAt: apiResp.created_at || 'Just now',
    technicalDetails,
    apiResponse: apiResp,
  };
}

/**
 * Reconstructs an AnalysisApiResponse from a stored database record retrieved
 * via GET /api/history/{analysis_id} without re-executing ML inference.
 */
export function adaptStoredAnalysisToApiResponse(stored: any): AnalysisApiResponse {
  const channel = stored.metadata?.channel || stored.channel || 'auto';
  const resolvedChannel = (stored.metadata?.resolved_channel || stored.channel || 'sms').toLowerCase() as 'sms' | 'email' | 'url' | 'qr';
  
  return {
    channel: channel,
    resolved_channel: resolvedChannel,
    prediction: stored.result?.prediction || 'Unknown',
    risk_score: typeof stored.result?.risk_score === 'number' ? stored.result.risk_score : 0,
    confidence: typeof stored.result?.confidence === 'number' ? stored.result.confidence : 0,
    reasons: Array.isArray(stored.explanation?.reasons) ? stored.explanation.reasons : [],
    indicators: Array.isArray(stored.explanation?.indicators) ? stored.explanation.indicators : [],
    recommendation: stored.explanation?.recommendation || '',
    tier1: stored.result?.tier1,
    tier2: stored.result?.tier2,
    tier3: stored.explanation?.tier3,
    qr_decoded_payload: stored.result?.qr_decoded_payload,
    qr_payload_type: stored.result?.qr_payload_type,
    qr_delegated_url: stored.result?.qr_delegated_url,
    qr_codes_detected: stored.result?.qr_codes_detected,
    qr_payloads: stored.result?.qr_payloads,
    qr_payload_types: stored.result?.qr_payload_types,
    analysis_id: stored.analysis_id || stored.id,
    created_at: stored.created_at,
    schema_version: stored.metadata?.schema_version || '1.0',
  };
}

/**
 * Transforms a complete stored analysis session into the AnalysisResult and
 * session input fields required by the workspace views without rerunning ML inference.
 */
export function adaptStoredAnalysisToResult(stored: any): {
  result: AnalysisResult;
  submittedInput: string;
  selectedModel: AnalysisType;
  emailSubject?: string;
} {
  const apiResp = adaptStoredAnalysisToApiResponse(stored);
  const rawInput = stored.input?.input || stored.input?.url || stored.input?.text || '';
  const emailSubject = stored.input?.subject || undefined;
  const submittedInput = emailSubject ? `Subject: ${emailSubject}\n\n${rawInput}` : rawInput;
  const selectedModel = (apiResp.resolved_channel || apiResp.channel || 'auto') as AnalysisType;
  const analysisId = stored.analysis_id || stored.id || `hist-${Date.now()}`;
  
  const result = adaptApiResponseToResult(apiResp, rawInput || submittedInput, analysisId);

  return {
    result,
    submittedInput: submittedInput || (apiResp.resolved_channel === 'qr' ? 'QR Code Matrix Analysis' : 'Security Analysis Input'),
    selectedModel,
    emailSubject,
  };
}

