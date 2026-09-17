"""
Investigation: Determine the nature of phishing_email.csv
Is it a separate source, a combined dataset, a processed/derived version, or something else?
"""
import pandas as pd
import numpy as np
import os
import hashlib

DATA_DIR = r"c:\Users\Digit\Desktop\CyberNexus\data\email"
PHISHING_FILE = "phishing_email.csv"
SOURCE_FILES = ["CEAS_08.csv", "Enron.csv", "Ling.csv", "Nazario.csv", "Nigerian_Fraud.csv", "SpamAssasin.csv"]

def safe_load(filepath):
    """Load CSV with encoding fallback."""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            df = pd.read_csv(filepath, encoding=enc, low_memory=False)
            return df, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Could not load {filepath} with any encoding")

# ============================================================
# 1. LOAD ALL FILES
# ============================================================
print("=" * 80)
print("1. LOADING ALL FILES")
print("=" * 80)

phishing_path = os.path.join(DATA_DIR, PHISHING_FILE)
phishing_df, phishing_enc = safe_load(phishing_path)
print(f"\nphishing_email.csv: {len(phishing_df)} rows, {len(phishing_df.columns)} cols, encoding={phishing_enc}")
print(f"  File size: {os.path.getsize(phishing_path):,} bytes")

source_dfs = {}
total_source_rows = 0
for f in SOURCE_FILES:
    fp = os.path.join(DATA_DIR, f)
    df, enc = safe_load(fp)
    source_dfs[f] = df
    total_source_rows += len(df)
    print(f"{f}: {len(df)} rows, {len(df.columns)} cols, encoding={enc}")
    print(f"  File size: {os.path.getsize(fp):,} bytes")

# ============================================================
# 2. COMPARE SCHEMAS
# ============================================================
print("\n" + "=" * 80)
print("2. SCHEMA COMPARISON")
print("=" * 80)

phishing_cols = set(phishing_df.columns)
print(f"\nphishing_email.csv columns ({len(phishing_cols)}): {list(phishing_df.columns)}")
print(f"phishing_email.csv dtypes:\n{phishing_df.dtypes}\n")

for f, df in source_dfs.items():
    src_cols = set(df.columns)
    shared = phishing_cols & src_cols
    only_phishing = phishing_cols - src_cols
    only_source = src_cols - phishing_cols
    print(f"\n--- {f} columns ({len(src_cols)}): {list(df.columns)}")
    print(f"    Shared with phishing_email: {shared}")
    print(f"    Only in phishing_email: {only_phishing}")
    print(f"    Only in {f}: {only_source}")
    print(f"    Schema match: {list(phishing_df.columns) == list(df.columns)}")

# ============================================================
# 3. ROW COUNT COMPARISON
# ============================================================
print("\n" + "=" * 80)
print("3. ROW COUNT COMPARISON")
print("=" * 80)
print(f"\nphishing_email.csv rows: {len(phishing_df)}")
print(f"Sum of all 6 source files: {total_source_rows}")
print(f"Difference (phishing - sum): {len(phishing_df) - total_source_rows}")
if total_source_rows > 0:
    print(f"Ratio (phishing / sum): {len(phishing_df) / total_source_rows:.4f}")

for f, df in source_dfs.items():
    print(f"  {f}: {len(df)} rows ({len(df)/total_source_rows*100:.1f}% of total)")

# ============================================================
# 4. OVERLAP CHECK (sample 100 rows from each source, check in phishing)
# ============================================================
print("\n" + "=" * 80)
print("4. OVERLAP CHECK (100-row samples from each source)")
print("=" * 80)

for f, src_df in source_dfs.items():
    sample_size = min(100, len(src_df))
    sample = src_df.sample(n=sample_size, random_state=42)
    
    shared_cols = list(set(phishing_df.columns) & set(src_df.columns))
    
    if not shared_cols:
        print(f"\n{f}: No shared columns with phishing_email - cannot check overlap")
        continue
    
    print(f"\n--- {f} (matching on shared cols: {shared_cols})")
    
    def normalize_df(df, cols):
        result = df[cols].copy()
        for c in cols:
            if result[c].dtype == object:
                result[c] = result[c].astype(str).str.strip().str.lower()
        return result
    
    norm_phishing = normalize_df(phishing_df, shared_cols)
    norm_sample = normalize_df(sample, shared_cols)
    
    merged = norm_sample.merge(norm_phishing, on=shared_cols, how='inner')
    match_count = len(merged)
    print(f"    Matched {match_count}/{sample_size} sample rows in phishing_email ({match_count/sample_size*100:.1f}%)")
    
    text_cols = [c for c in shared_cols if any(kw in c.lower() for kw in ['body', 'content', 'text', 'subject', 'message'])]
    if text_cols and text_cols != shared_cols:
        norm_phishing_text = normalize_df(phishing_df, text_cols)
        norm_sample_text = normalize_df(sample, text_cols)
        merged_text = norm_sample_text.merge(norm_phishing_text, on=text_cols, how='inner')
        print(f"    Text-column match ({text_cols}): {len(merged_text)}/{sample_size}")

# ============================================================
# 5. EXACT COLUMN COMPARISON (for schema-matching sources)
# ============================================================
print("\n" + "=" * 80)
print("5. EXACT COLUMN COMPARISON (for fully matching schemas)")
print("=" * 80)

for f, src_df in source_dfs.items():
    if list(phishing_df.columns) == list(src_df.columns):
        print(f"\n--- {f}: EXACT schema match!")
        dtype_match = all(phishing_df[c].dtype == src_df[c].dtype for c in phishing_df.columns)
        print(f"    Dtype match: {dtype_match}")
        for c in phishing_df.columns:
            if phishing_df[c].dtype in [np.int64, np.float64]:
                print(f"    {c} - phishing range: [{phishing_df[c].min()}, {phishing_df[c].max()}] | {f} range: [{src_df[c].min()}, {src_df[c].max()}]")
    else:
        shared = list(set(phishing_df.columns) & set(src_df.columns))
        if shared:
            print(f"\n--- {f}: Partial schema match ({len(shared)}/{len(phishing_df.columns)} cols)")
        else:
            print(f"\n--- {f}: No schema match")

# ============================================================
# 6. UNIQUE COLUMNS IN phishing_email
# ============================================================
print("\n" + "=" * 80)
print("6. UNIQUE COLUMNS IN phishing_email (not in any source)")
print("=" * 80)

all_source_cols = set()
for df in source_dfs.values():
    all_source_cols.update(df.columns)

unique_to_phishing = phishing_cols - all_source_cols
print(f"\nAll source columns combined: {all_source_cols}")
print(f"Columns unique to phishing_email: {unique_to_phishing if unique_to_phishing else 'NONE'}")

cols_in_sources_not_phishing = all_source_cols - phishing_cols
print(f"Columns in sources but NOT in phishing_email: {cols_in_sources_not_phishing if cols_in_sources_not_phishing else 'NONE'}")

# ============================================================
# 7. CHECK FOR SOURCE/DATASET IDENTIFIER COLUMN
# ============================================================
print("\n" + "=" * 80)
print("7. SOURCE/DATASET IDENTIFIER COLUMN CHECK")
print("=" * 80)

identifier_candidates = [c for c in phishing_df.columns if any(kw in c.lower() for kw in ['source', 'dataset', 'origin', 'file', 'category', 'type'])]
print(f"\nPotential identifier columns: {identifier_candidates}")

for c in identifier_candidates:
    vc = phishing_df[c].value_counts()
    print(f"\n  '{c}' value counts (top 20):")
    print(f"  {vc.head(20).to_string()}")
    print(f"  Unique values: {phishing_df[c].nunique()}")

source_names = ['CEAS', 'Enron', 'Ling', 'Nazario', 'Nigerian', 'SpamAssasin', 'Spam']
for c in phishing_df.columns:
    if phishing_df[c].dtype == object:
        sample_vals = phishing_df[c].dropna().head(1000).astype(str)
        for sn in source_names:
            if sample_vals.str.contains(sn, case=False).any():
                print(f"\n  Column '{c}' contains references to '{sn}'")
                break

# ============================================================
# 8. LABEL VALUE DISTRIBUTIONS
# ============================================================
print("\n" + "=" * 80)
print("8. LABEL VALUE DISTRIBUTIONS")
print("=" * 80)

label_candidates = [c for c in phishing_df.columns if any(kw in c.lower() for kw in ['label', 'class', 'spam', 'phish', 'target', 'is_', 'category'])]
print(f"\nLabel candidate columns in phishing_email: {label_candidates}")

if not label_candidates:
    for c in phishing_df.columns:
        if phishing_df[c].nunique() <= 10:
            label_candidates.append(c)
    print(f"Columns with <=10 unique values (possible labels): {label_candidates}")

for c in label_candidates:
    print(f"\n  phishing_email '{c}' distribution:")
    print(f"  {phishing_df[c].value_counts().to_string()}")

for f, src_df in source_dfs.items():
    src_label_candidates = [c for c in src_df.columns if any(kw in c.lower() for kw in ['label', 'class', 'spam', 'phish', 'target', 'is_', 'category'])]
    if not src_label_candidates:
        src_label_candidates = [c for c in src_df.columns if src_df[c].nunique() <= 10]
    for c in src_label_candidates:
        print(f"\n  {f} '{c}' distribution:")
        print(f"  {src_df[c].value_counts().to_string()}")

# ============================================================
# 9. SAMPLE ROWS FROM phishing_email
# ============================================================
print("\n" + "=" * 80)
print("9. SAMPLE ROWS FROM phishing_email.csv (first 5 rows)")
print("=" * 80)

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', 100)
pd.set_option('display.width', 200)

print(f"\n{phishing_df.head(5).to_string()}")

print("\n\nLast 5 rows:")
print(f"\n{phishing_df.tail(5).to_string()}")

print("\n\nRandom 5 rows:")
print(f"\n{phishing_df.sample(5, random_state=123).to_string()}")

# ============================================================
# 10. ADDITIONAL INVESTIGATION - FILE SIZE ANALYSIS
# ============================================================
print("\n" + "=" * 80)
print("10. ADDITIONAL ANALYSIS")
print("=" * 80)

total_source_size = sum(os.path.getsize(os.path.join(DATA_DIR, f)) for f in SOURCE_FILES)
phishing_size = os.path.getsize(phishing_path)
print(f"\nTotal source files size: {total_source_size:,} bytes")
print(f"phishing_email.csv size: {phishing_size:,} bytes")
print(f"Size ratio (phishing / total sources): {phishing_size / total_source_size:.4f}")
print(f"Size difference: {phishing_size - total_source_size:,} bytes")

print(f"\nDuplicate rows in phishing_email: {phishing_df.duplicated().sum()} / {len(phishing_df)}")
print(f"Null counts per column:")
print(phishing_df.isnull().sum().to_string())

print(f"\nphishing_email.csv info:")
print(f"  Shape: {phishing_df.shape}")
print(f"  Memory usage: {phishing_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)
