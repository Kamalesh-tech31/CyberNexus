"""
CyberNexus - Analysis Router
Phase 6C: Channel routing and model-grounded prediction endpoint.
"""

import re
import logging
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, status, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Union, Optional

from backend.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    QRNonUrlResponse,
    QRMultipleCodeResponse,
)
from backend.services.response_mapper import map_explanation_to_response
from backend.services.qr_service import decode_qr_image, decode_qr_base64_or_bytes, QRPayloadType
from backend.services.auth_service import get_current_user_optional

logger = logging.getLogger("cybernexus.analysis")
router = APIRouter(tags=["Analysis"])


def detect_channel(text: str) -> str:
    """
    Deterministic Heuristic Auto-Detect Router.
    Rules:
    1. URL regex / URL structure -> URL
    2. Email structure (Subject line OR From/To header + multi-line body) -> Email
    3. Fallback -> SMS
    """
    cleaned = text.strip()
    if not cleaned:
        return "sms"

    # 0. QR Image Heuristic (data URL)
    if cleaned.startswith("data:image/"):
        return "qr"

    # 1. URL Heuristic (conservative single-token URL/domain structure without internal whitespace)
    if not any(c.isspace() for c in cleaned):
        url_pattern = re.compile(
            r'^(https?://|www\.)\S+$|'
            r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}(/\S*)?$',
            re.IGNORECASE
        )
        if url_pattern.match(cleaned):
            return "url"

    # 2. Email Heuristic
    has_subject = bool(re.search(r'(?im)^subject\s*:', cleaned))
    has_header = bool(re.search(r'(?im)^(from|to)\s*:\s*.*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', cleaned))
    non_empty_lines = [line for line in cleaned.splitlines() if line.strip()]
    has_multiline = len(non_empty_lines) >= 2

    if has_subject or (has_header and has_multiline):
        return "email"

    # 3. Fallback to SMS
    return "sms"


def persist_analysis_if_authenticated(
    request: Request,
    current_user: Optional[Dict[str, Any]],
    channel: str,
    input_data: Dict[str, Any],
    response_dict: Dict[str, Any],
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    If current_user is authenticated and Supabase is configured:
      1. Upserts user in public.users to ensure foreign key integrity.
      2. Creates an analysis_sessions row.
      3. Creates user input message in analysis_messages.
      4. Creates assistant result/explanation/metadata message in analysis_messages.
      5. Injects analysis_id, created_at, schema_version="1.0" into response_dict.
    If guest:
      Returns response_dict with schema_version="1.0", analysis_id=None, created_at=None,
      with ZERO database writes.
    On persistence failure:
      Performs compensating cleanup (deletes created session if any)
      and raises HTTPException(500) so failure is not silently ignored.
    """
    response_dict["schema_version"] = "1.0"

    if not current_user:
        # Guest mode - strictly ephemeral, zero database writes
        return response_dict

    user_id = current_user.get("id")
    if not user_id:
        return response_dict

    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        logger.warning("Supabase is not configured; cannot persist authenticated analysis.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable for authenticated session persistence.",
        )

    session = None
    try:
        # 1. Ensure user profile exists
        supabase_service.ensure_user_exists(
            user_id=user_id,
            email=current_user.get("email"),
            display_name=(
                current_user.get("user_metadata", {}).get("full_name")
                or current_user.get("user_metadata", {}).get("display_name")
            ),
        )

        # 2. Derive title
        derived_title = (
            title
            or input_data.get("subject")
            or input_data.get("url")
            or input_data.get("input", "")[:50]
            or "Security Analysis"
        ).strip()
        if not derived_title:
            derived_title = "Security Analysis"

        # 3. Create Session
        session = supabase_service.create_analysis_session(
            user_id=user_id,
            channel=channel,
            title=derived_title[:100],
        )
        session_id = session["id"]

        # 4. Create User Message
        supabase_service.create_analysis_message(
            session_id=session_id,
            role="user",
            input_data=input_data,
        )

        # 5. Create Assistant Message
        result_payload = {
            "prediction": response_dict.get("prediction"),
            "risk_score": response_dict.get("risk_score"),
            "confidence": response_dict.get("confidence"),
            "tier1": response_dict.get("tier1"),
            "tier2": response_dict.get("tier2"),
            "qr_decoded_payload": response_dict.get("qr_decoded_payload"),
            "qr_payload_type": response_dict.get("qr_payload_type"),
            "qr_delegated_url": response_dict.get("qr_delegated_url"),
            "qr_codes_detected": response_dict.get("qr_codes_detected"),
            "qr_payloads": response_dict.get("qr_payloads"),
            "qr_payload_types": response_dict.get("qr_payload_types"),
        }
        explanation_payload = {
            "tier3": response_dict.get("tier3"),
            "reasons": response_dict.get("reasons"),
            "indicators": response_dict.get("indicators"),
            "recommendation": response_dict.get("recommendation"),
        }
        metadata_payload = {
            "channel": response_dict.get("channel"),
            "resolved_channel": response_dict.get("resolved_channel"),
            "schema_version": "1.0",
        }

        supabase_service.create_analysis_message(
            session_id=session_id,
            role="assistant",
            result=result_payload,
            explanation=explanation_payload,
            metadata=metadata_payload,
        )

        # 6. Inject persistence fields
        response_dict["analysis_id"] = session_id
        response_dict["created_at"] = session["created_at"]
        return response_dict

    except Exception as exc:
        if session and session.get("id"):
            try:
                supabase_service.delete_user_analysis(user_id, session["id"])
            except Exception:
                pass
        logger.error(f"Authenticated analysis persistence transaction failed: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis completed but persistence to user database failed.",
        )


@router.post(
    "/analyze",
    response_model=Union[AnalysisResponse, QRNonUrlResponse, QRMultipleCodeResponse],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def analyze_content(
    payload: AnalysisRequest,
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> Any:
    """
    Primary Content Analysis Endpoint.
    Validates request, resolves channel (explicit or auto-detected),
    executes model-grounded explainability through in-memory MLService,
    and maps the output to the unified CyberNexus progressive disclosure contract.
    """
    raw_input = (payload.input or "").strip()
    raw_subject = (payload.subject or "").strip()

    # 1. Validation: Reject completely empty input
    if not raw_input and not raw_subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input content cannot be empty."
        )

    # 2. Validation: Supported channels
    valid_channels = {"auto", "sms", "email", "url", "qr"}
    requested_channel = (payload.channel or "auto").strip().lower()
    if requested_channel not in valid_channels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported channel '{payload.channel}'. Supported channels: {', '.join(sorted(valid_channels))}."
        )

    # 3. Resolve Target Channel (Explicit override or Auto-Detect)
    if requested_channel == "auto":
        combined_text = f"Subject: {raw_subject}\n\n{raw_input}" if raw_subject else raw_input
        resolved_channel = detect_channel(combined_text)
    else:
        resolved_channel = requested_channel

    # 4. Access In-Memory ML Service
    ml_service = getattr(request.app.state, "ml_service", None)
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML Inference Service is not initialized.",
        )

    # 5. Execute Channel Prediction
    try:
        if resolved_channel == "qr":
            decode_result = decode_qr_base64_or_bytes(raw_input)
            if not decode_result.success:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=decode_result.error or "QR decode failed.",
                )

            if decode_result.multiple:
                content = {
                    "channel": "qr",
                    "resolved_channel": "qr",
                    "prediction": "Multiple QR Codes Detected",
                    "qr_codes_detected": len(decode_result.codes),
                    "qr_payloads": [c.raw_payload for c in decode_result.codes],
                    "qr_payload_types": [c.payload_type.value for c in decode_result.codes],
                    "risk_score": 0.0,
                    "confidence": 0.0,
                    "reasons": [
                        f"{len(decode_result.codes)} QR codes detected in the uploaded image.",
                        "Multiple codes: no single combined threat classification is produced.",
                        "Analyze each decoded URL individually using the URL channel.",
                    ],
                    "indicators": [],
                    "recommendation": (
                        "Multiple QR codes were found. "
                        "Submit each URL individually via the URL analysis channel for threat classification."
                    ),
                }
                content = persist_analysis_if_authenticated(
                    request,
                    current_user,
                    "qr",
                    {"input": "Multiple QR Payload"},
                    content,
                    "Multiple QR Codes",
                )
                return JSONResponse(status_code=200, content=content)

            code = decode_result.codes[0]
            if code.payload_type != QRPayloadType.URL:
                content = _non_url_qr_response(code.raw_payload, code.payload_type)
                content = persist_analysis_if_authenticated(
                    request,
                    current_user,
                    "qr",
                    {"input": code.raw_payload},
                    content,
                    f"QR Code: {code.payload_type.value}",
                )
                return JSONResponse(status_code=200, content=content)

            decoded_url = code.raw_payload
            explanation = ml_service.analyze_url(decoded_url)
            response_dict = map_explanation_to_response(
                explanation=explanation,
                resolved_channel="qr",
                raw_input_ref=None,
            )
            response_dict["qr_decoded_payload"] = decoded_url
            response_dict["qr_payload_type"] = QRPayloadType.URL.value
            response_dict["qr_delegated_url"] = decoded_url
            response_dict["channel"] = "qr"
            response_dict["resolved_channel"] = "qr"
            return persist_analysis_if_authenticated(
                request,
                current_user,
                "qr",
                {"input": decoded_url},
                response_dict,
                f"QR URL: {decoded_url[:50]}",
            )

        elif resolved_channel == "sms":
            explanation = ml_service.analyze_sms(raw_input)
        elif resolved_channel == "email":
            explanation = ml_service.analyze_email(subject=raw_subject, body=raw_input)
        elif resolved_channel == "url":
            explanation = ml_service.analyze_url(raw_input)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to process channel '{resolved_channel}'.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal inference error: {str(exc)}",
        )

    # 6. Format via Progressive Disclosure Response Adapter
    response_dict = map_explanation_to_response(
        explanation=explanation,
        resolved_channel=resolved_channel,
        raw_input_ref=None,
    )
    input_payload = {"input": raw_input}
    if raw_subject:
        input_payload["subject"] = raw_subject
    title = raw_subject if raw_subject else raw_input[:50]
    return persist_analysis_if_authenticated(
        request,
        current_user,
        resolved_channel,
        input_payload,
        response_dict,
        title,
    )


# ── QR Image Upload Endpoint ─────────────────────────────────────────────────

def _non_url_qr_response(decoded_payload: str, payload_type: QRPayloadType) -> Dict[str, Any]:
    """Build a structured response for non-URL QR payloads (no ML classification)."""
    type_labels = {
        QRPayloadType.WIFI:     "Wi-Fi Configuration",
        QRPayloadType.VCARD:    "vCard / Contact Information",
        QRPayloadType.MECARD:   "MeCard / Contact Information",
        QRPayloadType.GEO:      "Geographic Location",
        QRPayloadType.MAILTO:   "Email Link (mailto:)",
        QRPayloadType.TEL:      "Phone Number (tel:)",
        QRPayloadType.SMS_LINK: "SMS Link",
        QRPayloadType.TEXT:     "Plain Text",
    }
    label = type_labels.get(payload_type, "Unknown Payload Type")
    reasons = [
        f"QR code decoded successfully. Payload type: {label}.",
        "This payload type is not a URL and is not routed to the URL threat classifier.",
    ]
    return {
        "channel": "qr",
        "resolved_channel": "qr",
        "qr_decoded_payload": decoded_payload,
        "qr_payload_type": payload_type.value,
        "prediction": "Non-URL QR Payload",
        "risk_score": 0.0,
        "confidence": 0.0,
        "reasons": reasons,
        "indicators": [],
        "recommendation": (
            f"QR payload contains {label}. "
            "No URL threat analysis was performed. "
            "Review the decoded payload manually before acting on it."
        ),
    }


@router.post(
    "/analyze/qr",
    status_code=status.HTTP_200_OK,
    summary="Analyze a QR code image",
    description=(
        "Accepts a PNG/JPEG/WEBP/BMP image file, decodes all QR codes, "
        "and routes URL payloads through the existing CyberNexus URL analysis pipeline. "
        "Non-URL payloads are returned with their decoded content and no ML classification."
    ),
)
async def analyze_qr_image(
    request: Request,
    file: UploadFile = File(..., description="QR code image (PNG, JPEG, WEBP, BMP)"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> JSONResponse:
    """
    QR Resolve Engine endpoint.

    Flow:
      1. Validate and read uploaded image bytes.
      2. Decode QR code(s) via zxing-cpp.
      3. If multiple codes: return structured multi-code response.
      4. If single code URL: delegate to existing URL analysis pipeline.
      5. If single code non-URL: return decoded payload without ML classification.
    """
    # 1. Read image bytes (bounded)
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    try:
        image_bytes = await file.read(MAX_BYTES + 1)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc!s}",
        )

    if len(image_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the 10 MB limit.",
        )

    # 2. Validate MIME type (loose check — zxing/Pillow do the real validation)
    content_type = (file.content_type or "").lower()
    allowed_mime_prefixes = ("image/",)
    if content_type and not any(content_type.startswith(p) for p in allowed_mime_prefixes):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Upload a PNG, JPEG, WEBP, or BMP image.",
        )

    # 3. Decode QR
    decode_result = decode_qr_image(image_bytes)

    if not decode_result.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=decode_result.error or "QR decode failed.",
        )

    # 4. Multiple codes — return structured response, no single classification
    if decode_result.multiple:
        content = {
            "channel": "qr",
            "resolved_channel": "qr",
            "prediction": "Multiple QR Codes Detected",
            "qr_codes_detected": len(decode_result.codes),
            "qr_payloads": [c.raw_payload for c in decode_result.codes],
            "qr_payload_types": [c.payload_type.value for c in decode_result.codes],
            "risk_score": 0.0,
            "confidence": 0.0,
            "reasons": [
                f"{len(decode_result.codes)} QR codes detected in the uploaded image.",
                "Multiple codes: no single combined threat classification is produced.",
                "Analyze each decoded URL individually using the URL channel.",
            ],
            "indicators": [],
            "recommendation": (
                "Multiple QR codes were found. "
                "Submit each URL individually via the URL analysis channel for threat classification."
            ),
        }
        content = persist_analysis_if_authenticated(
            request,
            current_user,
            "qr",
            {"filename": file.filename, "type": "multiple_codes"},
            content,
            "Multiple QR Codes Detected",
        )
        return JSONResponse(status_code=200, content=content)

    # 5. Single code
    code = decode_result.codes[0]

    # 5a. Non-URL payload — return decoded content, no ML
    if code.payload_type != QRPayloadType.URL:
        content = _non_url_qr_response(code.raw_payload, code.payload_type)
        content = persist_analysis_if_authenticated(
            request,
            current_user,
            "qr",
            {"filename": file.filename, "payload": code.raw_payload},
            content,
            f"QR Code: {code.payload_type.value}",
        )
        return JSONResponse(status_code=200, content=content)

    # 5b. URL payload — delegate to existing URL analysis pipeline
    ml_service = getattr(request.app.state, "ml_service", None)
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML Inference Service is not initialized.",
        )

    decoded_url = code.raw_payload
    try:
        explanation = ml_service.analyze_url(decoded_url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"URL analysis error: {exc!s}",
        )

    # Map using existing response adapter, then inject QR-specific fields
    response_dict = map_explanation_to_response(
        explanation=explanation,
        resolved_channel="qr",
        raw_input_ref=None,
    )
    response_dict["qr_decoded_payload"] = decoded_url
    response_dict["qr_payload_type"] = QRPayloadType.URL.value
    response_dict["qr_delegated_url"] = decoded_url
    # Override channel to 'qr' (map_explanation_to_response sets it from the explanation)
    response_dict["channel"] = "qr"
    response_dict["resolved_channel"] = "qr"

    response_dict = persist_analysis_if_authenticated(
        request,
        current_user,
        "qr",
        {"filename": file.filename, "url": decoded_url},
        response_dict,
        f"QR URL: {decoded_url[:50]}",
    )
    return JSONResponse(status_code=200, content=response_dict)

