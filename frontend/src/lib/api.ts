/**
 * CyberNexus - Frontend API Client
 * Phase 6E: Real HTTP client connecting frontend to FastAPI /api/analyze endpoint.
 */

import { AnalysisType } from '../types';

// API Base URL - sourced from Vite environment configuration
const env = (typeof import.meta !== 'undefined' && (import.meta as any).env) ? (import.meta as any).env : ((typeof process !== 'undefined' ? process.env : {}) as any);
const API_BASE_URL = env?.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 15000; // 15 seconds

export interface AnalysisApiRequest {
  channel: AnalysisType;
  input: string;
  subject?: string | null;
}

export interface Tier1ApiResponse {
  verdict: string;
  confidence: number; // 0.0 - 1.0
  confidence_band: 'high' | 'medium' | 'low';
  summary: string;
}

export interface Tier2FlagApiResponse {
  label: string;
  status: string;
  detail: string;
}

export interface Tier2ApiResponse {
  flags: Tier2FlagApiResponse[];
  confidence_breakdown: Record<string, number>;
}

export interface FeatureContributionApiResponse {
  feature: string;
  value: number;
  contribution: number;
  direction: 'increases_risk' | 'decreases_risk';
}

export interface TextSignalApiResponse {
  token: string;
  weight: number;
  contribution?: number;
  direction?: 'increases_risk' | 'decreases_risk';
  source?: 'subject' | 'body' | null;
}

export interface ModelMetadataApiResponse {
  model_name?: string;
  architecture?: string;
  calibration?: string;
  model_version: string;
  trained_on: string;
  operational_threshold?: number;
  note: string;
}

export interface Tier3ApiResponse {
  feature_contributions: FeatureContributionApiResponse[];
  top_text_signals?: TextSignalApiResponse[] | null;
  bias_term?: number;
  model_metadata: ModelMetadataApiResponse;
}

export interface AnalysisApiResponse {
  channel: string;
  prediction: string;
  risk_score: number; // 0.0 - 100.0
  confidence: number; // 0.0 - 1.0
  reasons: string[];
  indicators: string[];
  recommendation: string;
  raw_input_ref?: string | null;
  tier1?: Tier1ApiResponse;
  tier2?: Tier2ApiResponse;
  tier3?: Tier3ApiResponse;
  resolved_channel: 'sms' | 'email' | 'url' | 'qr';
  qr_decoded_payload?: string;
  qr_payload_type?: string;
  qr_delegated_url?: string;
  qr_codes_detected?: number;
  qr_payloads?: string[];
  qr_payload_types?: string[];
  analysis_id?: string;
  created_at?: string;
  schema_version?: string;
}

export class ApiError extends Error {
  status: number;
  isTimeout: boolean;

  constructor(message: string, status: number = 0, isTimeout: boolean = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.isTimeout = isTimeout;
  }
}

/**
 * Executes a POST request to /api/analyze with strict timeout and comprehensive error handling.
 */
export async function analyzeContent(
  payload: AnalysisApiRequest,
  accessToken?: string | null,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<AnalysisApiResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const url = `${API_BASE_URL}/api/analyze`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        channel: payload.channel,
        input: payload.input,
        subject: payload.subject || undefined,
      }),
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!response.ok) {
      let errorDetail = `Request failed with status ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorDetail = errorJson.detail;
        }
      } catch {
        // Fallback to default message if JSON parsing fails
      }

      if (response.status === 401) {
        throw new ApiError(errorDetail || 'Authentication required or session expired.', 401);
      } else if (response.status === 501) {
        throw new ApiError(
          errorDetail || 'QR Code Matrix analysis pipeline is scheduled for Phase 6E.',
          501
        );
      } else if (response.status === 400) {
        throw new ApiError(errorDetail || 'Invalid input or unsupported channel.', 400);
      } else if (response.status === 503) {
        throw new ApiError('ML Inference Service is currently unavailable. Please ensure backend is running.', 503);
      } else {
        throw new ApiError(errorDetail || `Server error (${response.status})`, response.status);
      }
    }

    const data: AnalysisApiResponse = await response.json();
    return data;
  } catch (error: any) {
    clearTimeout(timer);

    if (error.name === 'AbortError') {
      throw new ApiError(
        `Analysis request timed out after ${timeoutMs / 1000}s. The server may be busy or unreachable.`,
        408,
        true
      );
    }

    if (error instanceof ApiError) {
      throw error;
    }

    // Network / connection failure
    throw new ApiError(
      `Unable to connect to CyberNexus backend at ${API_BASE_URL}. Ensure FastAPI server is running on port 8000.`,
      0
    );
  }
}

/**
 * Executes a multipart/form-data POST request to /api/analyze/qr with an image file.
 */
export async function analyzeQRFile(
  file: File | Blob,
  accessToken?: string | null,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<AnalysisApiResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${API_BASE_URL}/api/analyze/qr`;
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!response.ok) {
      let errorDetail = `QR Analysis failed with status ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorDetail = errorJson.detail;
        }
      } catch {
        // Fallback
      }
      if (response.status === 401) {
        throw new ApiError(errorDetail || 'Authentication required or session expired.', 401);
      }
      throw new ApiError(errorDetail, response.status);
    }

    const data: AnalysisApiResponse = await response.json();
    return data;
  } catch (error: any) {
    clearTimeout(timer);
    if (error.name === 'AbortError') {
      throw new ApiError(`QR analysis timed out after ${timeoutMs / 1000}s.`, 408, true);
    }
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      `Unable to connect to CyberNexus backend at ${API_BASE_URL}. Ensure FastAPI server is running on port 8000.`,
      0
    );
  }
}

// ── Phase 6F-3: History & Account Management Primitives ─────────────────────

export interface HistoryItemApiResponse {
  analysis_id: string;
  title: string;
  channel: string;
  created_at: string;
  updated_at?: string;
}

export async function fetchUserHistory(
  accessToken: string,
  limit: number = 50,
  offset: number = 0
): Promise<HistoryItemApiResponse[]> {
  const url = `${API_BASE_URL}/api/history?limit=${limit}&offset=${offset}`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to fetch history (${response.status})`, response.status);
  }
  return response.json();
}

export async function fetchUserAnalysis(
  analysisId: string,
  accessToken: string
): Promise<any> {
  const url = `${API_BASE_URL}/api/history/${analysisId}`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to fetch analysis (${response.status})`, response.status);
  }
  return response.json();
}

export async function deleteUserAnalysis(
  analysisId: string,
  accessToken: string
): Promise<boolean> {
  const url = `${API_BASE_URL}/api/history/${analysisId}`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to delete analysis (${response.status})`, response.status);
  }
  return true;
}

export async function deleteAllUserHistory(accessToken: string): Promise<boolean> {
  const url = `${API_BASE_URL}/api/history`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to clear history (${response.status})`, response.status);
  }
  return true;
}

export async function deleteUserAccount(accessToken: string): Promise<boolean> {
  const url = `${API_BASE_URL}/api/account`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    let errorDetail = `Failed to delete account (${response.status})`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Fallback to status text
    }
    throw new ApiError(errorDetail, response.status);
  }
  return true;
}

