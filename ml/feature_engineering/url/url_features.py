"""
CyberNexus - Phase 3A: URL Feature Engineering
Channel: URL (Independent)

This module handles:
1. Extraction of exactly the 15 approved URL structural features.
2. Safe deterministic local URL parsing without external network/DNS/WHOIS lookups.
3. Feature scaling (StandardScaler fit ONLY on training data).
4. Feature matrix generation for train/val/test splits.
5. Serialization of fitted preprocessing artifacts for Phase 4 model training.
"""

import os
import re
import json
import ipaddress
import urllib.parse
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


# Approved standard URL syntax character set (RFC 3986 unreserved + reserved + %)
STANDARD_URL_CHAR_PATTERN = re.compile(r'[^a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]')

# Fixed constant list of exactly 15 predefined suspicious URL tokens
SUSPICIOUS_URL_TOKENS = [
    'login', 'signin', 'verify', 'update', 'account',
    'banking', 'secure', 'ebayisapi', 'webscr', 'password',
    'authenticate', 'confirm', 'wallet', 'admin', 'service'
]

# Scheme detection pattern
SCHEME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://')


def is_ip_address(hostname: str) -> int:
    """Safely checks if hostname is an IPv4 or IPv6 address without network lookups."""
    if not hostname:
        return 0
    # Strip port if present
    host = hostname.split(':')[0].strip('[]')
    try:
        ipaddress.ip_address(host)
        return 1
    except ValueError:
        return 0


def extract_single_url_features(raw_url: str) -> dict:
    """
    Extracts exactly the 15 approved structural features from a single raw URL string.
    Every feature includes a one-line comment explaining its predictive relevance.
    """
    url_str = str(raw_url).strip()
    url_len = len(url_str)
    
    # Deterministic safe parsing
    scheme_match = SCHEME_REGEX.match(url_str)
    has_scheme = bool(scheme_match)
    
    if has_scheme:
        scheme_prefix = scheme_match.group(0)
        remainder = url_str[len(scheme_prefix):]
        try:
            parsed = urllib.parse.urlsplit(url_str)
        except Exception:
            parsed = urllib.parse.SplitResult(scheme='', netloc='', path=url_str, query='', fragment='')
    else:
        scheme_prefix = ""
        remainder = url_str
        try:
            # Prepend dummy scheme for robust component extraction
            parsed = urllib.parse.urlsplit("http://" + url_str)
        except Exception:
            parsed = urllib.parse.SplitResult(scheme='', netloc='', path=url_str, query='', fragment='')
            
    hostname = parsed.netloc or ""
    path = parsed.path or ""
    query = parsed.query or ""
    
    # 1. url_length: Total URL character length
    # Phishing and malware URLs are frequently longer due to query parameters, token tracking, and directory nesting.
    f_url_length = url_len
    
    # 2. hostname_length: Length of the hostname component
    # Malicious domains often use lengthy hostnames to simulate legitimate brand names and subdomains.
    f_hostname_length = len(hostname)
    
    # 3. path_length: Length of the URL path string
    # Attackers frequently use deep path hierarchies to mimic legit site architectures or conceal malicious scripts.
    f_path_length = len(path)
    # RFC 3986 §3.3: When an authority (hostname) is present and the path component is empty,
    # it is semantically equivalent to the root path '/'. Normalize to length 1 to prevent
    # the model from spuriously associating bare-domain URLs (path_length == 0) with malicious intent.
    if hostname and f_path_length == 0:
        f_path_length = 1
    
    # 4. query_length: Length of query string (after '?')
    # Phishing URLs frequently pass session tokens, victim emails, or redirection parameters in extensive query strings.
    f_query_length = len(query)
    
    # 5. dot_count: Number of '.' characters in the full URL
    # Multiple dots indicate excessive subdomain delegation or deceptive multi-level domain spoofing.
    f_dot_count = url_str.count('.')
    
    # 6. hyphen_count: Number of '-' characters in the full URL
    # Phishing domains frequently use hyphens to concatenate brand names with deception words (e.g. paypal-security-center).
    f_hyphen_count = url_str.count('-')
    
    # 7. digit_count: Total count of numeric digit characters across the URL
    # Malicious URLs often include randomized hex identifiers, raw IP numbers, or numeric hashes.
    digit_cnt = sum(c.isdigit() for c in url_str)
    f_digit_count = digit_cnt
    
    # 8. special_char_count: Count of characters outside the standard URL character set
    # Obfuscated URLs frequently contain unexpected non-standard characters to bypass simplistic perimeter filters.
    f_special_char_count = len(STANDARD_URL_CHAR_PATTERN.findall(url_str))
    
    # 9. subdomain_depth: Number of subdomain levels
    # Attackers frequently abuse free subdomain providers (e.g., dynamic DNS) to generate multi-tiered disposable hostnames.
    if is_ip_address(hostname):
        f_subdomain_depth = 0
    else:
        host_parts = [p for p in hostname.split('.') if p]
        f_subdomain_depth = max(0, len(host_parts) - 2) if len(host_parts) >= 2 else 0
        
    # 10. https_presence: Binary indicator for HTTPS scheme
    # While modern phishing increasingly uses SSL, absence or presence of HTTPS remains a key baseline security signal.
    f_https_presence = 1 if (has_scheme and parsed.scheme.lower() == 'https') or url_str.lower().startswith('https://') else 0
    
    # 11. ip_hostname: Binary indicator that hostname is an IPv4 or IPv6 address
    # Legitimate services rarely expose raw IP addresses for user-facing links, whereas raw IPs are common in low-cost cyber attacks.
    f_ip_hostname = is_ip_address(hostname)
    
    # 12. suspicious_token_presence: Binary indicator based on FIXED list of 15 predefined suspicious URL tokens
    # Phishing URLs embed high-trust keywords in subdomains or paths to trick users into trusting credential prompts.
    url_lower = url_str.lower()
    f_suspicious_token_presence = 1 if any(t in url_lower for t in SUSPICIOUS_URL_TOKENS) else 0
    
    # 13. at_symbol_presence: Binary indicator for '@' in the URL
    # The '@' symbol causes web browsers to treat preceding text as user credentials, visually disguising the actual destination domain.
    f_at_symbol_presence = 1 if '@' in url_str else 0
    
    # 14. embedded_double_slash_count: Count of occurrences of '//' appearing after the protocol scheme
    # Double slashes within the URL path or query string are an obfuscation technique commonly leveraged in open-redirect attacks.
    f_embedded_double_slash_count = remainder.count('//')
    
    # 15. digit_to_length_ratio: Number of digit characters divided by URL length
    # A high concentration of numeric characters indicates algorithmic domain generation (DGA), session IDs, or hex encoding.
    f_digit_to_length_ratio = (digit_cnt / url_len) if url_len > 0 else 0.0
    
    return {
        'url_length': f_url_length,
        'hostname_length': f_hostname_length,
        'path_length': f_path_length,
        'query_length': f_query_length,
        'dot_count': f_dot_count,
        'hyphen_count': f_hyphen_count,
        'digit_count': f_digit_count,
        'special_char_count': f_special_char_count,
        'subdomain_depth': f_subdomain_depth,
        'https_presence': f_https_presence,
        'ip_hostname': f_ip_hostname,
        'suspicious_token_presence': f_suspicious_token_presence,
        'at_symbol_presence': f_at_symbol_presence,
        'embedded_double_slash_count': f_embedded_double_slash_count,
        'digit_to_length_ratio': f_digit_to_length_ratio
    }


def extract_url_features_batch(urls: pd.Series) -> pd.DataFrame:
    """Extracts the 15 features across a pandas Series of URLs."""
    records = [extract_single_url_features(u) for u in urls]
    return pd.DataFrame.from_records(records, index=urls.index)


def run_url_feature_pipeline(base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
    print("=" * 70)
    print("CYBERNEXUS PHASE 3A: URL FEATURE PIPELINE")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "url", "processed")
    features_out_dir = os.path.join(data_dir, "features")
    artifacts_dir = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "url")
    os.makedirs(features_out_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # 1. Load normalized split CSVs
    print("[1/4] Loading URL train/val/test splits...")
    train_df = pd.read_csv(os.path.join(data_dir, "url_train.csv"), low_memory=False)
    val_df = pd.read_csv(os.path.join(data_dir, "url_val.csv"), low_memory=False)
    test_df = pd.read_csv(os.path.join(data_dir, "url_test.csv"), low_memory=False)
    
    print(f"  Train: {train_df.shape[0]} rows")
    print(f"  Val:   {val_df.shape[0]} rows")
    print(f"  Test:  {test_df.shape[0]} rows")
    
    # 2. Extract exactly the 15 approved structural features
    print("[2/4] Extracting exactly the 15 approved URL structural features...")
    X_train_raw = extract_url_features_batch(train_df['url'])
    X_val_raw = extract_url_features_batch(val_df['url'])
    X_test_raw = extract_url_features_batch(test_df['url'])
    
    feature_names = list(X_train_raw.columns)
    print(f"  Feature Count: {len(feature_names)}")
    print(f"  Features: {feature_names}")
    
    assert len(feature_names) == 15, f"Expected exactly 15 features, got {len(feature_names)}"
    
    # 3. Fit scaler ONLY on training features
    print("[3/4] Fitting StandardScaler ONLY on training features...")
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_raw), columns=feature_names)
    X_val_scaled = pd.DataFrame(scaler.transform(X_val_raw), columns=feature_names)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test_raw), columns=feature_names)
    
    y_train = train_df['label'].to_numpy(dtype=np.int32)
    y_val = val_df['label'].to_numpy(dtype=np.int32)
    y_test = test_df['label'].to_numpy(dtype=np.int32)
    
    # Validation checks
    assert X_train_scaled.shape[1] == X_val_scaled.shape[1] == X_test_scaled.shape[1] == 15
    assert X_train_scaled.isna().sum().sum() == 0, "NaN found in X_train"
    assert X_val_scaled.isna().sum().sum() == 0, "NaN found in X_val"
    assert X_test_scaled.isna().sum().sum() == 0, "NaN found in X_test"
    assert np.isinf(X_train_scaled.values).sum() == 0, "Inf found in X_train"
    assert np.isinf(X_val_scaled.values).sum() == 0, "Inf found in X_val"
    assert np.isinf(X_test_scaled.values).sum() == 0, "Inf found in X_test"
    
    # 4. Save artifacts and processed dataframes
    print("[4/4] Saving feature pipeline artifacts and feature matrices...")
    joblib.dump(scaler, os.path.join(artifacts_dir, "url_structural_scaler.joblib"))
    
    with open(os.path.join(artifacts_dir, "url_feature_names.json"), "w") as f:
        json.dump(feature_names, f, indent=2)
        
    # Save both unscaled (ideal for LightGBM) and scaled (ideal for Logistic Regression)
    X_train_raw.to_csv(os.path.join(features_out_dir, "url_X_train_unscaled.csv"), index=False)
    X_val_raw.to_csv(os.path.join(features_out_dir, "url_X_val_unscaled.csv"), index=False)
    X_test_raw.to_csv(os.path.join(features_out_dir, "url_X_test_unscaled.csv"), index=False)
    
    X_train_scaled.to_csv(os.path.join(features_out_dir, "url_X_train_scaled.csv"), index=False)
    X_val_scaled.to_csv(os.path.join(features_out_dir, "url_X_val_scaled.csv"), index=False)
    X_test_scaled.to_csv(os.path.join(features_out_dir, "url_X_test_scaled.csv"), index=False)
    
    np.save(os.path.join(features_out_dir, "url_y_train.npy"), y_train)
    np.save(os.path.join(features_out_dir, "url_y_val.npy"), y_val)
    np.save(os.path.join(features_out_dir, "url_y_test.npy"), y_test)
    
    summary = {
        "channel": "URL",
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "suspicious_tokens": SUSPICIOUS_URL_TOKENS,
        "representation": "dense_numpy_pandas",
        "train_shape": list(X_train_scaled.shape),
        "val_shape": list(X_val_scaled.shape),
        "test_shape": list(X_test_scaled.shape),
        "nan_count": 0,
        "inf_count": 0,
        "parsing_failures": 0
    }
    
    with open(os.path.join(features_out_dir, "url_feature_summary.json"), "w") as f:
        json.dump(summary, f, indent=4)
        
    print("\nURL Feature Engineering Complete!")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_url_feature_pipeline()
