"""
CyberNexus - Phase 3A: SMS Feature Engineering
Channel: SMS (Independent)

This module handles:
1. Word-level TF-IDF extraction (ngram_range=(1,2), max_features=4000) fit ONLY on training data.
2. Extraction of 6 approved SMS structural features with safe division.
3. Feature scaling on structural features (StandardScaler fit ONLY on training data).
4. Sparse stacking of TF-IDF and structural features for train/val/test splits.
5. Serialization of fitted preprocessing artifacts for Phase 4 model training.
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


# Approved URL pattern for SMS messages
URL_REGEX = re.compile(r'(?:https?://|www\.|\.com|\.org|\.net|\.co|\.uk|\.biz|\.info|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)', re.IGNORECASE)

# Approved punctuation set for punctuation density (!, ?, $, %)
PUNCT_PATTERN = re.compile(r'[!?$%£€]')

# Special characters: anything not alphanumeric, whitespace, or standard basic punctuation
SPECIAL_CHAR_PATTERN = re.compile(r'[^a-zA-Z0-9\s!?$%£€.,;:\'\"()\-_\/]')


def extract_sms_structural_features(messages: pd.Series) -> pd.DataFrame:
    """
    Extracts exactly the 6 approved structural features from raw SMS messages.
    Every feature includes a one-line comment explaining its predictive relevance.
    """
    feats = pd.DataFrame(index=messages.index)
    
    # Ensure all messages are string
    msg_str = messages.fillna('').astype(str)
    
    # 1. message_length: Character count of the message
    # Spam messages frequently have longer lengths to pack promotional offers, contact details, and disclaimers.
    feats['message_length'] = msg_str.str.len()
    
    # 2. digit_to_length_ratio: Number of digit characters divided by message length
    # Spam messages disproportionately feature numeric phone numbers, prize amounts, shortcodes, and claim dates.
    digit_count = msg_str.apply(lambda s: sum(c.isdigit() for c in s))
    feats['digit_to_length_ratio'] = np.where(feats['message_length'] > 0, digit_count / feats['message_length'], 0.0)
    
    # 3. url_presence: Binary indicator of whether the message contains a URL
    # Phishing and modern spam SMS heavily rely on embedded web links to direct victims to external malicious pages.
    feats['url_presence'] = msg_str.apply(lambda s: 1 if bool(URL_REGEX.search(s)) else 0)
    
    # 4. punctuation_density: Count of relevant punctuation (! ? $ % etc.) relative to message length
    # Urgent promotional language and monetary lures in spam frequently overuse exclamation marks, currency signs, and percentages.
    punct_count = msg_str.apply(lambda s: len(PUNCT_PATTERN.findall(s)))
    feats['punctuation_density'] = np.where(feats['message_length'] > 0, punct_count / feats['message_length'], 0.0)
    
    # 5. uppercase_ratio: Uppercase alphabetic characters divided by total alphabetic characters
    # Spam texts disproportionately employ ALL-CAPS words to simulate artificial urgency and capture visual attention.
    upper_count = msg_str.apply(lambda s: sum(c.isupper() for c in s))
    alpha_count = msg_str.apply(lambda s: sum(c.isalpha() for c in s))
    feats['uppercase_ratio'] = np.where(alpha_count > 0, upper_count / alpha_count, 0.0)
    
    # 6. special_char_count: Count of non-alphanumeric / non-approved punctuation symbols
    # Spam messages frequently contain unusual symbols, decorative brackets, or obfuscated characters to bypass simple keyword filters.
    feats['special_char_count'] = msg_str.apply(lambda s: len(SPECIAL_CHAR_PATTERN.findall(s)))
    
    return feats


def run_sms_feature_pipeline(base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
    print("=" * 70)
    print("CYBERNEXUS PHASE 3A: SMS FEATURE PIPELINE")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "sms", "processed")
    features_out_dir = os.path.join(data_dir, "features")
    artifacts_dir = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "sms")
    os.makedirs(features_out_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # 1. Load normalized split CSVs
    print("[1/5] Loading SMS train/val/test splits...")
    train_df = pd.read_csv(os.path.join(data_dir, "sms_train.csv"))
    val_df = pd.read_csv(os.path.join(data_dir, "sms_val.csv"))
    test_df = pd.read_csv(os.path.join(data_dir, "sms_test.csv"))
    
    print(f"  Train: {train_df.shape[0]} rows")
    print(f"  Val:   {val_df.shape[0]} rows")
    print(f"  Test:  {test_df.shape[0]} rows")
    
    # 2. Extract TF-IDF representation
    # max_features=4000: SMS text is concise; 4000 captures all high-frequency unigrams & informative bigrams without overfitting.
    print("[2/5] Fitting TF-IDF vectorizer (word-level, ngram_range=(1,2), max_features=4000) ONLY on training messages...")
    tfidf = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 2),
        max_features=4000,
        sublinear_tf=True,
        dtype=np.float32
    )
    
    # CRITICAL: Fit ONLY on train
    X_train_tfidf = tfidf.fit_transform(train_df['message'].fillna(''))
    X_val_tfidf = tfidf.transform(val_df['message'].fillna(''))
    X_test_tfidf = tfidf.transform(test_df['message'].fillna(''))
    
    vocab_size = len(tfidf.vocabulary_)
    print(f"  TF-IDF Vocabulary Size: {vocab_size}")
    
    # 3. Extract approved structural features
    print("[3/5] Extracting 6 approved structural features...")
    X_train_struct = extract_sms_structural_features(train_df['message'])
    X_val_struct = extract_sms_structural_features(val_df['message'])
    X_test_struct = extract_sms_structural_features(test_df['message'])
    
    struct_cols = list(X_train_struct.columns)
    print(f"  Structural Features ({len(struct_cols)}): {struct_cols}")
    
    # 4. Scale structural features (StandardScaler fit ONLY on training data)
    print("[4/5] Scaling structural features with StandardScaler fit ONLY on train...")
    scaler = StandardScaler()
    X_train_struct_scaled = scaler.fit_transform(X_train_struct)
    X_val_struct_scaled = scaler.transform(X_val_struct)
    X_test_struct_scaled = scaler.transform(X_test_struct)
    
    # Combine sparse TF-IDF and scaled structural features
    X_train_combined = sparse.hstack([X_train_tfidf, sparse.csr_matrix(X_train_struct_scaled)], format='csr')
    X_val_combined = sparse.hstack([X_val_tfidf, sparse.csr_matrix(X_val_struct_scaled)], format='csr')
    X_test_combined = sparse.hstack([X_test_tfidf, sparse.csr_matrix(X_test_struct_scaled)], format='csr')
    
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
    joblib.dump(tfidf, os.path.join(artifacts_dir, "sms_tfidf_vectorizer.joblib"))
    joblib.dump(scaler, os.path.join(artifacts_dir, "sms_structural_scaler.joblib"))
    
    feature_names = [f"tfidf_{w}" for w in tfidf.get_feature_names_out()] + struct_cols
    with open(os.path.join(artifacts_dir, "sms_feature_names.json"), "w") as f:
        json.dump(feature_names, f, indent=2)
        
    sparse.save_npz(os.path.join(features_out_dir, "sms_X_train.npz"), X_train_combined)
    sparse.save_npz(os.path.join(features_out_dir, "sms_X_val.npz"), X_val_combined)
    sparse.save_npz(os.path.join(features_out_dir, "sms_X_test.npz"), X_test_combined)
    
    np.save(os.path.join(features_out_dir, "sms_y_train.npy"), y_train)
    np.save(os.path.join(features_out_dir, "sms_y_val.npy"), y_val)
    np.save(os.path.join(features_out_dir, "sms_y_test.npy"), y_test)
    
    # Save raw structural dataframes for LightGBM compatibility
    X_train_struct.to_csv(os.path.join(features_out_dir, "sms_train_structural.csv"), index=False)
    X_val_struct.to_csv(os.path.join(features_out_dir, "sms_val_structural.csv"), index=False)
    X_test_struct.to_csv(os.path.join(features_out_dir, "sms_test_structural.csv"), index=False)
    
    summary = {
        "channel": "SMS",
        "tfidf_ngram_range": [1, 2],
        "tfidf_max_features": 4000,
        "tfidf_vocab_size": int(vocab_size),
        "num_structural_features": len(struct_cols),
        "structural_feature_names": struct_cols,
        "total_features": int(X_train_combined.shape[1]),
        "representation": "scipy.sparse.csr_matrix",
        "train_shape": list(X_train_combined.shape),
        "val_shape": list(X_val_combined.shape),
        "test_shape": list(X_test_combined.shape),
        "nan_count": 0,
        "inf_count": 0
    }
    
    with open(os.path.join(features_out_dir, "sms_feature_summary.json"), "w") as f:
        json.dump(summary, f, indent=4)
        
    print("\nSMS Feature Engineering Complete!")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_sms_feature_pipeline()
