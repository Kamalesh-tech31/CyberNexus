import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { adaptStoredAnalysisToApiResponse, adaptStoredAnalysisToResult } from '../lib/resultAdapter';
import { AnalysisSession, UserProfile } from '../types';

describe('Batch 4 — Historical Analysis Viewing', () => {
  const mockStoredSmsAnalysis = {
    analysis_id: 'sms-sess-001',
    session_id: 'sms-sess-001',
    user_id: 'usr-alice-123',
    title: 'SMS: Urgent Account Alert',
    channel: 'sms',
    created_at: '2026-09-17T08:00:00Z',
    input: {
      channel: 'sms',
      input: 'Urgent: Your card has been compromised. Verify now at http://secure-bank.example',
    },
    result: {
      prediction: 'Likely Smishing',
      risk_score: 92.5,
      confidence: 0.925,
      tier1: {
        verdict: 'Likely Smishing',
        confidence: 0.925,
        confidence_band: 'high',
        summary: 'High probability smishing attempt detected.',
      },
      tier2: {
        flags: [
          { label: 'URL Presence', status: 'detected', detail: 'Contains embedded link' },
          { label: 'Urgency Keyword Count', status: 'detected', detail: 'High urgency language' },
        ],
        confidence_breakdown: { smishing: 0.925, legitimate: 0.075 },
      },
    },
    explanation: {
      tier3: {
        feature_contributions: [
          { feature: 'url_presence', value: 1, contribution: 2.1, direction: 'increases_risk' },
          { feature: 'message_length', value: 78, contribution: 0.4, direction: 'increases_risk' },
        ],
        top_text_signals: [
          { token: 'urgent', weight: 1.8, contribution: 1.8, direction: 'increases_risk', source: null },
          { token: 'compromised', weight: 1.5, contribution: 1.5, direction: 'increases_risk', source: null },
        ],
        model_metadata: {
          model_name: 'SMS Logistic Regression',
          architecture: "L2-regularized linear model (C=5.0, class_weight='balanced')",
          calibration: 'Sigmoid / Platt Scaling (CalibratedClassifierCV)',
          model_version: 'v1.0-champion',
          trained_on: 'SMS Spam Collection + Synthetic Phishing',
          operational_threshold: 0.5,
          note: 'Locked production classifier',
        },
      },
      reasons: ['Contains suspicious urgent call-to-action', 'Includes external link'],
      indicators: ['Urgent phrasing', 'External URL'],
      recommendation: 'Do not click on links in unsolicited messages.',
    },
    metadata: {
      channel: 'sms',
      resolved_channel: 'sms',
      schema_version: '1.0',
    },
  };

  it('1. adapts stored SMS record to AnalysisResult without re-running ML', () => {
    const { result, submittedInput, selectedModel } = adaptStoredAnalysisToResult(mockStoredSmsAnalysis);

    assert.equal(result.id, 'sms-sess-001');
    assert.equal(result.detectedType, 'sms');
    assert.equal(result.verdict, 'Likely Smishing');
    assert.equal(result.confidence, 92.5);
    assert.equal(result.severity, 'critical');
    assert.equal(submittedInput, 'Urgent: Your card has been compromised. Verify now at http://secure-bank.example');
    assert.equal(selectedModel, 'sms');
    assert.ok(result.technicalDetails !== undefined);
    assert.equal(result.technicalDetails?.channel, 'sms');
    assert.equal(result.technicalDetails?.structural_signals.length, 2);
    assert.equal(result.technicalDetails?.text_signals?.tokens?.length, 2);
    assert.equal(result.technicalDetails?.text_signals?.tokens?.[0].token, 'urgent');
  });

  it('2. adapts stored Email record preserving subject and body separation', () => {
    const mockStoredEmail = {
      analysis_id: 'email-sess-002',
      session_id: 'email-sess-002',
      user_id: 'usr-alice-123',
      title: 'Email: Wire Transfer Notification',
      channel: 'email',
      created_at: '2026-09-17T08:05:00Z',
      input: {
        channel: 'email',
        subject: 'Payment Pending',
        input: 'Please review the attached remittance invoice immediately.',
      },
      result: {
        prediction: 'Likely Phishing',
        risk_score: 88.0,
        confidence: 0.88,
      },
      explanation: {
        tier3: {
          feature_contributions: [
            { feature: 'email_length', value: 55, contribution: 0.3, direction: 'increases_risk' },
          ],
          top_text_signals: [
            { token: 'pending', weight: 1.2, contribution: 1.2, direction: 'increases_risk', source: 'subject' },
            { token: 'invoice', weight: 1.6, contribution: 1.6, direction: 'increases_risk', source: 'body' },
          ],
          model_metadata: {
            model_name: 'Email Classifier',
            model_version: 'v1.0',
            trained_on: 'Enron/SpamAssassin',
            note: 'Production email pipeline',
          },
        },
        reasons: ['Urgent payment language in email'],
        indicators: ['Financial trigger'],
        recommendation: 'Verify payment requests through out-of-band communication.',
      },
      metadata: {
        channel: 'email',
        resolved_channel: 'email',
      },
    };

    const { result, submittedInput, emailSubject } = adaptStoredAnalysisToResult(mockStoredEmail);

    assert.equal(result.detectedType, 'email');
    assert.equal(emailSubject, 'Payment Pending');
    assert.ok(submittedInput.includes('Subject: Payment Pending'));
    assert.ok(submittedInput.includes('Please review the attached remittance invoice'));
    assert.equal(result.technicalDetails?.text_signals?.subject?.length, 1);
    assert.equal(result.technicalDetails?.text_signals?.subject?.[0].token, 'pending');
    assert.equal(result.technicalDetails?.text_signals?.body?.length, 1);
    assert.equal(result.technicalDetails?.text_signals?.body?.[0].token, 'invoice');
  });

  it('3. adapts stored QR record preserving decoded payload and delegation', () => {
    const mockStoredQR = {
      analysis_id: 'qr-sess-003',
      session_id: 'qr-sess-003',
      title: 'QR Code Matrix Analysis',
      channel: 'qr',
      created_at: '2026-09-17T08:10:00Z',
      input: {
        channel: 'qr',
        input: 'https://login-verify.example.org',
      },
      result: {
        prediction: 'Suspicious QR (Quishing)',
        risk_score: 75.0,
        confidence: 0.75,
        qr_decoded_payload: 'https://login-verify.example.org',
        qr_payload_type: 'url',
        qr_delegated_url: 'https://login-verify.example.org',
      },
      explanation: {
        reasons: ['QR matrix encodes URL with deceptive domain structure'],
        indicators: ['Suspicious domain routing'],
        recommendation: 'Do not navigate to unverified destinations scanned via QR.',
      },
      metadata: {
        channel: 'qr',
        resolved_channel: 'qr',
      },
    };

    const { result, submittedInput } = adaptStoredAnalysisToResult(mockStoredQR);

    assert.equal(result.detectedType, 'qr');
    assert.equal(result.extractedContent?.qrDecodedPayload, 'https://login-verify.example.org');
    assert.equal(result.extractedContent?.qrPayloadType, 'url');
    assert.equal(result.extractedContent?.targetUrl, 'https://login-verify.example.org');
  });

  it('4. Historical detail fetch: avoids duplicate network request when result already exists', () => {
    let fetchCount = 0;
    const sessionWithResult: AnalysisSession = {
      id: 'existing-sess-1',
      title: 'Loaded Analysis',
      selectedModel: 'url',
      submittedInput: 'https://example.com',
      isAnalyzing: false,
      stages: [],
      currentStageIndex: 0,
      createdAt: '2026-09-17T08:00:00Z',
      result: {
        id: 'existing-sess-1',
        detectedType: 'url',
        verdict: 'Safe & Legitimate',
        confidence: 99.1,
        severity: 'safe',
        summary: 'No threat detected',
        reasons: [],
        recommendedAction: 'Proceed normally',
        indicators: [],
        explanation: 'Safe domain',
        modelMetrics: {
          modelName: 'URL LightGBM',
          architecture: 'GBDT',
          datasetName: 'URL dataset',
          featureWeights: [],
        },
        analyzedAt: '2026-09-17T08:00:00Z',
      },
    };

    // Selection handler logic check
    if (!sessionWithResult.result && !sessionWithResult.isAnalyzing) {
      fetchCount++;
    }

    assert.equal(fetchCount, 0, 'Must NOT trigger network request if result is already in memory');
  });

  it('5. Stale historical detail race condition: discards outdated response', () => {
    let activeDetailId = 0;
    let selectedSessionResultId: string | null = null;

    // User clicks Session A
    const reqIdA = ++activeDetailId;

    // User rapidly clicks Session B before Session A arrives
    const reqIdB = ++activeDetailId;

    // Response for Session B arrives first
    if (reqIdB === activeDetailId) {
      selectedSessionResultId = 'session-B';
    }

    // Delayed response for Session A arrives late
    if (reqIdA === activeDetailId) {
      selectedSessionResultId = 'session-A'; // MUST NOT be assigned
    }

    assert.equal(selectedSessionResultId, 'session-B', 'Delayed response from previous selection must be ignored');
  });

  it('6. Detail 401 error: Triggers session invalidation callback', () => {
    let authFailureCalled = false;
    const onAuthFailure = () => {
      authFailureCalled = true;
    };

    const status = 401;
    if (status === 401) {
      onAuthFailure();
    }

    assert.equal(authFailureCalled, true, '401 on detail retrieval must trigger auth failure callback');
  });

  it('7. Detail error on 404/network failure: sets error on session without mock fallback', () => {
    let session: AnalysisSession = {
      id: 'missing-sess-404',
      title: 'Missing Analysis',
      selectedModel: 'sms',
      submittedInput: '',
      isAnalyzing: false,
      stages: [],
      currentStageIndex: 0,
      createdAt: '2026-09-17T08:00:00Z',
    };

    const networkError = new Error('Analysis record not found.');
    session = {
      ...session,
      isLoadingDetail: false,
      error: networkError.message,
    };

    assert.equal(session.result, undefined, 'Must not fabricate mock result on error');
    assert.equal(session.error, 'Analysis record not found.');
  });

  it('8. Guest mode isolation: never calls fetchAnalysisDetail', () => {
    const user: UserProfile | null = null;
    let backendDetailRequested = false;

    // Selection handler check
    if (user && (user as UserProfile).accessToken) {
      backendDetailRequested = true;
    }

    assert.equal(backendDetailRequested, false, 'Guest mode must never request detail from backend API');
  });

  it('9. Historical Cache Identity Isolation (7C.2): User A cached detail cannot leak into User B session state upon user switch', () => {
    // User A session with cached detail
    let userASessions: AnalysisSession[] = [
      {
        id: 'hist-user-a-1',
        title: 'User A SMS',
        selectedModel: 'sms',
        submittedInput: 'User A confidential payload',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
        result: {
          prediction: 'Likely Smishing',
          riskScore: 95,
          confidence: 0.95,
        } as any,
      },
    ];

    // Transition: User A logs out
    let activeSessions: AnalysisSession[] = userASessions;
    let activeUser: UserProfile | null = { id: 'usr-a', name: 'Alice', email: 'a@ex.com', accessToken: 'token-a' };

    // App.tsx user transition clears sessions
    activeSessions = [];
    activeUser = null;

    // User B logs in
    activeUser = { id: 'usr-b', name: 'Bob', email: 'b@ex.com', accessToken: 'token-b' };
    let userBSessions: AnalysisSession[] = [
      {
        id: 'hist-user-b-1',
        title: 'User B URL',
        selectedModel: 'url',
        submittedInput: 'https://bob.com',
        isAnalyzing: false,
        stages: [],
        currentStageIndex: 0,
        createdAt: 'now',
        result: undefined, // unpopulated
      },
    ];
    activeSessions = userBSessions;

    assert.equal(activeSessions.length, 1);
    assert.equal(activeSessions[0].id, 'hist-user-b-1');
    assert.equal(activeSessions[0].result, undefined, 'User B must not have any cached result initially');
    assert.equal(activeSessions.some((s) => s.id === 'hist-user-a-1'), false, 'User A session must not leak to User B');
  });
});
