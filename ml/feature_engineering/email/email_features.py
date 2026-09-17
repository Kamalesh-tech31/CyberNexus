"""
CyberNexus - Phase 3A: Email Feature Engineering
Channel: Email (Independent)

This module handles:
1. Dedicated Word-level Subject TF-IDF (ngram_range=(1,2), max_features=3000) fit ONLY on train.
2. Dedicated Word-level Body TF-IDF (ngram_range=(1,2), max_features=7000) fit ONLY on train.
3. Extraction of 6 approved Email structural features (skipping 3 ungrounded features with documented reasons).
4. Feature scaling on structural features (StandardScaler fit ONLY on training data).
5. Sparse stacking of [Subject TF-IDF] + [Body TF-IDF] + [Structural Features].
6. Serialization of fitted preprocessing artifacts for Phase 4 model training.
"""

import os
import re
import json
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler


# Approved URL pattern for Email text
URL_REGEX = re.compile(r'(?:https?://|www\.|\.com|\.org|\.net|\.co|\.uk|\.biz|\.info|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)', re.IGNORECASE)

# All-caps word pattern (length >= 2)
ALL_CAPS_WORD_PATTERN = re.compile(r'\b[A-Z]{2,}\b')

# Fixed constant list of exactly 20 predefined urgency words/phrases
URGENCY_KEYWORDS = [
    'urgent', 'immediately', 'act now', 'action required', 'account suspended',
    'verify your account', 'password expire', 'security alert', 'final notice', 'unauthorized',
    'threat', 'compromised', 'banking', 'billing', 'confirm identity',
    'restricted', 'update payment', 'lockout', 'suspended', 'limited time'
]

# Compile regex for fast urgency keyword matching
URGENCY_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(k) for k in URGENCY_KEYWORDS) + r')\b', re.IGNORECASE)


def extract_email_structural_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts approved Email structural features where the dataset genuinely supports them.
    
    Implemented Features (6):
    1. email_length: Body character count
    2. url_count: Count of URLs in email
    3. digit_count: Count of digits in subject + body
    4. exclamation_count: Count of '!' in subject + body
    5. all_caps_word_count: Count of all-uppercase words (len >= 2)
    6. urgency_keyword_count: Match count of fixed 20 urgency keywords
    
    Skipped Features (3):
    7. sender_domain_mismatch: SKIPPED - Enron/Ling lack sender fields (~40% of records), and DKIM/SPF headers are absent.
    8. attachment_presence: SKIPPED - No authentic attachment metadata exists across the normalized sources.
    9. html_to_text_ratio: SKIPPED - Raw HTML was stripped/standardized in multiple sources, making comparison unreliable.
    """
    feats = pd.DataFrame(index=df.index)
    
    subj_str = df['subject'].fillna('').astype(str)
    body_str = df['body'].fillna('').astype(str)
    full_text = subj_str + "\n" + body_str
    
    # 1. email_length: Body character count
    # Phishing lures tend to be concise and actionable, whereas legitimate corporate emails and newsletters vary widely in length.
    feats['email_length'] = body_str.str.len()
    
    # 2. url_count: Number of URLs present in the email
    # Phishing emails heavily rely on embedded hyperlinks to credential-harvesting pages or malicious payload distribution sites.
    feats['url_count'] = full_text.apply(lambda s: len(URL_REGEX.findall(s)))
    
    # 3. digit_count: Number of digit characters in subject and body
    # Financial scams, fake invoices, and lottery phishing frequently contain reference codes, monetary amounts, and phone numbers.
    feats['digit_count'] = full_text.apply(lambda s: sum(c.isdigit() for c in s))
    
    # 4. exclamation_count: Number of '!' characters in subject and body
    # Spam emails frequently use excessive exclamation marks to fabricate psychological excitement or synthetic urgency.
    feats['exclamation_count'] = full_text.apply(lambda s: s.count('!'))
    
    # 5. all_caps_word_count: Number of words written entirely in uppercase with length >= 2
    # Scammers frequently write words in ALL-CAPS (e.g., URGENT, NOTICE, SUSPENDED) to draw immediate user attention.
    feats['all_caps_word_count'] = full_text.apply(lambda s: len(ALL_CAPS_WORD_PATTERN.findall(s)))
    
    # 6. urgency_keyword_count: Match count using a FIXED list of 20 predefined urgency words/phrases
    # Phishing campaigns exploit fear and time-pressure (e.g., account suspension, immediate action) to bypass critical thinking.
    feats['urgency_keyword_count'] = full_text.apply(lambda s: len(URGENCY_REGEX.findall(s)))
    
    return feats


def run_email_feature_pipeline(base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
    print("=" * 70)
    print("CYBERNEXUS PHASE 3A: EMAIL FEATURE PIPELINE")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "email", "processed")
    features_out_dir = os.path.join(data_dir, "features")
    artifacts_dir = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "email")
    os.makedirs(features_out_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # 1. Load normalized split CSVs
    print("[1/5] Loading Email train/val/test splits...")
    train_df = pd.read_csv(os.path.join(data_dir, "email_train.csv"), low_memory=False)
    val_df = pd.read_csv(os.path.join(data_dir, "email_val.csv"), low_memory=False)
    test_df = pd.read_csv(os.path.join(data_dir, "email_test.csv"), low_memory=False)
    
    print(f"  Train: {train_df.shape[0]} rows")
    print(f"  Val:   {val_df.shape[0]} rows")
    print(f"  Test:  {test_df.shape[0]} rows")
    
    # 2. Extract Subject TF-IDF (Dedicated Word-level, max_features=3000)
    # max_features=3000: Subject lines are short; 3000 captures all high-value subject keywords and deception bigrams.
    print("[2/5] Fitting Subject TF-IDF vectorizer (word-level, ngram_range=(1,2), max_features=3000) ONLY on training subjects...")
    subj_tfidf = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 2),
        max_features=3000,
        sublinear_tf=True,
        dtype=np.float32
    )
    
    # Fit ONLY on train subject
    X_train_subj_tfidf = subj_tfidf.fit_transform(train_df['subject'].fillna(''))
    X_val_subj_tfidf = subj_tfidf.transform(val_df['subject'].fillna(''))
    X_test_subj_tfidf = subj_tfidf.transform(test_df['subject'].fillna(''))
    
    subj_vocab_size = len(subj_tfidf.vocabulary_)
    print(f"  Subject TF-IDF Vocabulary Size: {subj_vocab_size}")
    
    # 3. Extract Body TF-IDF (Dedicated Word-level, max_features=7000)
    # max_features=7000: Body texts are longer; 7000 captures domain vocabulary across Enron, CEAS, Ling, etc. while remaining CPU/RAM-efficient.
    print("[3/5] Fitting Body TF-IDF vectorizer (word-level, ngram_range=(1,2), max_features=7000) ONLY on training bodies...")
    body_tfidf = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 2),
        max_features=7000,
        sublinear_tf=True,
        dtype=np.float32
    )
    
    # Fit ONLY on train body
    X_train_body_tfidf = body_tfidf.fit_transform(train_df['body'].fillna(''))
    X_val_body_tfidf = body_tfidf.transform(val_df['body'].fillna(''))
    X_test_body_tfidf = body_tfidf.transform(test_df['body'].fillna(''))
    
    body_vocab_size = len(body_tfidf.vocabulary_)
    print(f"  Body TF-IDF Vocabulary Size: {body_vocab_size}")
    
    # 4. Extract approved structural features
    print("[4/5] Extracting 6 approved structural features (3 skipped with documented rationale)...")
    X_train_struct = extract_email_structural_features(train_df)
    X_val_struct = extract_email_structural_features(val_df)
    X_test_struct = extract_email_structural_features(test_df)
    
    struct_cols = list(X_train_struct.columns)
    print(f"  Implemented Structural Features ({len(struct_cols)}): {struct_cols}")
    
    # Scale structural features with StandardScaler fit ONLY on training data
    scaler = StandardScaler()
    X_train_struct_scaled = scaler.fit_transform(X_train_struct)
    X_val_struct_scaled = scaler.transform(X_val_struct)
    X_test_struct_scaled = scaler.transform(X_test_struct)
    
    # Combine: [Subject TF-IDF] + [Body TF-IDF] + [Structural Features]
    X_train_combined = sparse.hstack([X_train_subj_tfidf, X_train_body_tfidf, sparse.csr_matrix(X_train_struct_scaled)], format='csr')
    X_val_combined = sparse.hstack([X_val_subj_tfidf, X_val_body_tfidf, sparse.csr_matrix(X_val_struct_scaled)], format='csr')
    X_test_combined = sparse.hstack([X_test_subj_tfidf, X_test_body_tfidf, sparse.csr_matrix(X_test_struct_scaled)], format='csr')
    
    y_train = train_df['label'].to_numpy(dtype=np.int32)
    y_val = val_df['label'].to_numpy(dtype=np.int32)
    y_test = test_df['label'].to_numpy(dtype=np.int32)
    
    print(f"  Final Combined Train Matrix Shape: {X_train_combined.shape}")
    print(f"  Final Combined Val Matrix Shape:   {X_val_combined.shape}")
    print(f"  Final Combined Test Matrix Shape:  {X_test_combined.shape}")
    
    # Validation checks
    assert X_train_combined.shape[1] == X_val_combined.shape[1] == X_test_combined.shape[1]
    assert np.isnan(X_train_combined.data).sum() == 0, "NaN found in X_train"
    assert np.isnan(X_val_combined.data).sum() == 0, "NaN found in X_val"
    assert np.isnan(X_test_combined.data).sum() == 0, "NaN found in X_test"
    assert np.isinf(X_train_combined.data).sum() == 0, "Inf found in X_train"
    assert np.isinf(X_val_combined.data).sum() == 0, "Inf found in X_val"
    assert np.isinf(X_test_combined.data).sum() == 0, "Inf found in X_test"
    
    # 5. Save serialized artifacts and matrices
    print("[5/5] Saving feature pipelines and processed feature matrices...")
    joblib.dump(subj_tfidf, os.path.join(artifacts_dir, "email_subject_tfidf_vectorizer.joblib"))
    joblib.dump(body_tfidf, os.path.join(artifacts_dir, "email_body_tfidf_vectorizer.joblib"))
    joblib.dump(scaler, os.path.join(artifacts_dir, "email_structural_scaler.joblib"))
    
    subj_features = [f"subj_tfidf_{w}" for w in subj_tfidf.get_feature_names_out()]
    body_features = [f"body_tfidf_{w}" for w in body_tfidf.get_feature_names_out()]
    all_feature_names = subj_features + body_features + struct_cols
    
    with open(os.path.join(artifacts_dir, "email_feature_names.json"), "w") as f:
        json.dump(all_feature_names, f, indent=2)
        
    sparse.save_npz(os.path.join(features_out_dir, "email_X_train.npz"), X_train_combined)
    sparse.save_npz(os.path.join(features_out_dir, "email_X_val.npz"), X_val_combined)
    sparse.save_npz(os.path.join(features_out_dir, "email_X_test.npz"), X_test_combined)
    
    np.save(os.path.join(features_out_dir, "email_y_train.npy"), y_train)
    np.save(os.path.join(features_out_dir, "email_y_val.npy"), y_val)
    np.save(os.path.join(features_out_dir, "email_y_test.npy"), y_test)
    
    # Save raw structural dataframes for LightGBM compatibility
    X_train_struct.to_csv(os.path.join(features_out_dir, "email_train_structural.csv"), index=False)
    X_val_struct.to_csv(os.path.join(features_out_dir, "email_val_structural.csv"), index=False)
    X_test_struct.to_csv(os.path.join(features_out_dir, "email_test_structural.csv"), index=False)
    
    summary = {
        "channel": "Email",
        "subject_tfidf_ngram_range": [1, 2],
        "subject_tfidf_max_features": 3000,
        "subject_vocab_size": int(subj_vocab_size),
        "body_tfidf_ngram_range": [1, 2],
        "body_tfidf_max_features": 7000,
        "body_vocab_size": int(body_vocab_size),
        "implemented_structural_features": struct_cols,
        "skipped_structural_features": [
            {"name": "sender_domain_mismatch", "reason": "Enron & Ling datasets lack sender/from fields (~40% of records), and authentication headers are absent."},
            {"name": "attachment_presence", "reason": "No authentic attachment metadata field exists across the 6 normalized source datasets."},
            {"name": "html_to_text_ratio", "reason": "Raw HTML was stripped/standardized in multiple sources, making comparison unreliable."}
        ],
        "total_features": int(X_train_combined.shape[1]),
        "representation": "scipy.sparse.csr_matrix",
        "train_shape": list(X_train_combined.shape),
        "val_shape": list(X_val_combined.shape),
        "test_shape": list(X_test_combined.shape),
        "nan_count": 0,
        "inf_count": 0
    }
    
    with open(os.path.join(features_out_dir, "email_feature_summary.json"), "w") as f:
        json.dump(summary, f, indent=4)
        
    print("\nEmail Feature Engineering Complete!")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_email_feature_pipeline()
