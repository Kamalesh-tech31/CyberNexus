export type AnalysisType = 'auto' | 'email' | 'sms' | 'url' | 'qr';

export type ThreatSeverity = 'critical' | 'high' | 'medium' | 'low' | 'safe';

export type VerdictType = 
  | 'Likely Phishing'
  | 'Likely Smishing'
  | 'Malicious URL'
  | 'Suspicious QR (Quishing)'
  | 'Suspicious Content'
  | 'Safe & Legitimate'
  | 'Non-URL QR Payload'
  | 'Multiple QR Codes Detected';

export interface ExecutionStage {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed';
  timestamp?: string;
  detail?: string;
}

export interface DetectedIndicator {
  id: string;
  category: 'URL' | 'Text' | 'Sender' | 'Semantic' | 'QR Code' | 'Header';
  name: string;
  severity: ThreatSeverity;
  description: string;
  metricValue?: string;
}

export interface ModelMetrics {
  modelName: string;
  architecture: string;
  accuracy?: number | null; // runtime benchmark metrics omitted unless supplied by backend
  precision?: number | null;
  recall?: number | null;
  f1Score?: number | null;
  inferenceLatency?: string | null;
  datasetName: string;
  samplesTrained?: string | null;
  featureWeights: { feature: string; weight: number }[];
}

export interface AnalysisResult {
  id: string;
  detectedType: 'email' | 'sms' | 'url' | 'qr';
  verdict: VerdictType;
  confidence: number; // 0 - 100 percentage
  severity: ThreatSeverity;
  summary: string;
  reasons: string[];
  recommendedAction: string;
  extractedContent?: {
    qrDecodedPayload?: string;
    qrPayloadType?: string;
    targetUrl?: string;
    senderAddress?: string;
    subjectLine?: string;
    messageBody?: string;
  };
  indicators: DetectedIndicator[];
  explanation: string;
  modelMetrics: ModelMetrics;
  analyzedAt: string;
  /** Phase 5B model-grounded explainability payload (optional, absent for legacy/QR results) */
  technicalDetails?: TechnicalDetails;
  /** Phase 6D progressive-disclosure API response payload */
  apiResponse?: any;
}

export interface AnalysisSession {
  id: string;
  title: string;
  selectedModel: AnalysisType;
  submittedInput: string;
  uploadedImage?: string | null; // data url or image name
  isAnalyzing: boolean;
  isLoadingDetail?: boolean;
  stages: ExecutionStage[];
  currentStageIndex: number;
  result?: AnalysisResult;
  error?: string;
  createdAt: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role?: string;
  avatarUrl?: string;
  accessToken?: string;
}

// ── Phase 5B: Model-Grounded Explainability ────────────────────────────────

export interface StructuralSignal {
  feature: string;
  feature_label: string;
  value: number;
  raw_value_display: string;
  contribution: number;
  direction: 'increases_risk' | 'decreases_risk';
  description: string;
}

export interface TextSignal {
  token: string;
  weight: number;
  contribution: number;
  direction: 'increases_risk' | 'decreases_risk';
  origin?: 'subject' | 'body' | null;  // null for SMS
}

export interface ExplainabilityModelMetadata {
  channel: string;
  model_name: string;
  architecture: string;
  calibration: string;
  model_version: string;
  trained_on: string;
  operational_threshold: number;
  note: string;
}

/** Shape that matches the Python UnifiedExplanation.to_dict() output */
export interface TechnicalDetails {
  channel: string;
  predicted_class: number;
  predicted_label: string;
  raw_score: number;
  calibrated_confidence: number;
  operational_threshold: number;
  structural_signals: StructuralSignal[];
  /** SMS: { tokens: TextSignal[] } | Email: { subject?: TextSignal[], body?: TextSignal[] } | URL: null */
  text_signals: { tokens?: TextSignal[]; subject?: TextSignal[]; body?: TextSignal[] } | null;
  model_metadata: ExplainabilityModelMetadata;
}
