"""
SMS Spam Collection Dataset Audit Script
Audits: c:\Users\Digit\Desktop\CyberNexus\data\sms\
"""

import os
import pandas as pd
import re
from collections import Counter

DATA_DIR = r"c:\Users\Digit\Desktop\CyberNexus\data\sms"
README_PATH = os.path.join(DATA_DIR, "readme")
SMS_PATH = os.path.join(DATA_DIR, "SMSSpamCollection")

SEPARATOR = "=" * 80

# ── 1. Read and display the readme ──────────────────────────────────────────
print(SEPARATOR)
print("1. README FILE CONTENTS")
print(SEPARATOR)
for enc in ["utf-8", "latin-1", "cp1252"]:
    try:
        with open(README_PATH, "r", encoding=enc) as f:
            readme_text = f.read()
        print(f"[Encoding used: {enc}]")
        print(readme_text)
        break
    except (UnicodeDecodeError, FileNotFoundError) as e:
        print(f"  Failed with {enc}: {e}")

# ── 2. Inspect SMSSpamCollection ────────────────────────────────────────────
print(SEPARATOR)
print("2. INSPECTING SMSSpamCollection")
print(SEPARATOR)

# 2a. Load as tab-separated, no header
df = None
load_enc = None
for enc in ["utf-8", "latin-1", "cp1252"]:
    try:
        df = pd.read_csv(
            SMS_PATH,
            sep="\t",
            header=None,
            names=["label", "message"],
            encoding=enc,
            on_bad_lines="warn",
            engine="python",
        )
        load_enc = enc
        print(f"[Loaded successfully with encoding: {enc}]")
        break
    except Exception as e:
        print(f"  Failed with {enc}: {e}")

if df is None:
    print("ERROR: Could not load the file with any encoding.")
    exit(1)

# 2b. Basic shape
print(f"\n-- Row count   : {len(df)}")
print(f"-- Column count: {df.shape[1]}")
print(f"-- Columns     : {list(df.columns)}")
print(f"-- Dtypes      :\n{df.dtypes.to_string()}")

# 2c. First 5 sample records
print(f"\n-- First 5 records:")
for i, row in df.head(5).iterrows():
    print(f"  [{i}] label={row['label']!r}  message={row['message']!r:.120}")

# 2d. Label column analysis
print(f"\n-- Label column unique values: {sorted(df['label'].unique())}")
label_counts = df["label"].value_counts()
label_pcts = df["label"].value_counts(normalize=True) * 100
print("-- Label distribution:")
for lbl in label_counts.index:
    print(f"   {lbl:>6s} : {label_counts[lbl]:>5d}  ({label_pcts[lbl]:.2f}%)")

# 2e. Missing values
print(f"\n-- Missing values per column:")
for col in df.columns:
    n_null = df[col].isna().sum()
    n_empty = (df[col].astype(str).str.strip() == "").sum() if col == "message" else 0
    print(f"   {col:>10s} : null={n_null}, empty_string={n_empty}")

# 2f. Exact duplicate rows
n_exact_dup = df.duplicated().sum()
print(f"\n-- Exact duplicate rows: {n_exact_dup}")
if n_exact_dup > 0:
    print("   Sample duplicated rows:")
    dups = df[df.duplicated(keep=False)].sort_values(["label", "message"])
    for i, row in dups.head(10).iterrows():
        print(f"     [{i}] {row['label']!r}  {row['message']!r:.100}")

# 2g. Duplicate messages (ignoring label)
n_msg_dup = df["message"].duplicated().sum()
print(f"\n-- Duplicate messages (ignoring label): {n_msg_dup}")
if n_msg_dup > 0:
    dup_msgs = df[df["message"].duplicated(keep=False)]
    dup_msg_groups = dup_msgs.groupby("message")["label"].apply(list)
    # show messages that appear with DIFFERENT labels (label conflicts)
    conflicts = {msg: lbls for msg, lbls in dup_msg_groups.items() if len(set(lbls)) > 1}
    print(f"   Messages with conflicting labels: {len(conflicts)}")
    if conflicts:
        for msg, lbls in list(conflicts.items())[:5]:
            print(f"     msg={msg!r:.80}  labels={lbls}")

# 2h. Text encoding quality
print(f"\n-- Text encoding quality checks:")

# Empty messages
empty_msgs = df[df["message"].isna() | (df["message"].astype(str).str.strip() == "")]
print(f"   Empty/blank messages: {len(empty_msgs)}")

# Messages with replacement character (garbled)
garbled = df[df["message"].astype(str).str.contains("\ufffd", na=False)]
print(f"   Messages with replacement char (U+FFFD): {len(garbled)}")

# Messages with non-ASCII characters
non_ascii = df[df["message"].astype(str).str.contains(r"[^\x00-\x7F]", regex=True, na=False)]
print(f"   Messages with non-ASCII characters: {len(non_ascii)}")
if len(non_ascii) > 0:
    print(f"   Sample non-ASCII messages (up to 5):")
    for i, row in non_ascii.head(5).iterrows():
        # find the non-ascii chars
        chars = set(re.findall(r"[^\x00-\x7F]", str(row["message"])))
        print(f"     [{i}] chars={chars}  msg={row['message']!r:.100}")

# Messages with control characters (excluding normal whitespace)
ctrl = df[df["message"].astype(str).str.contains(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", regex=True, na=False)]
print(f"   Messages with control characters: {len(ctrl)}")

# Very short messages (< 3 chars)
short = df[df["message"].astype(str).str.len() < 3]
print(f"   Very short messages (< 3 chars): {len(short)}")
if len(short) > 0:
    for i, row in short.head(5).iterrows():
        print(f"     [{i}] label={row['label']!r}  msg={row['message']!r}")

# Very long messages (> 500 chars)
long_msgs = df[df["message"].astype(str).str.len() > 500]
print(f"   Very long messages (> 500 chars): {len(long_msgs)}")

# Message length statistics
lengths = df["message"].astype(str).str.len()
print(f"   Message length stats: min={lengths.min()}, max={lengths.max()}, "
      f"mean={lengths.mean():.1f}, median={lengths.median():.1f}")

# 2i. UCI SMS Spam Collection v1 structure check
print(f"\n-- UCI SMS Spam Collection v1 structure verification:")
expected_labels = {"ham", "spam"}
actual_labels = set(df["label"].unique())
labels_ok = actual_labels == expected_labels
expected_rows = 5574  # known row count for UCI SMS Spam Collection v1
rows_ok = len(df) == expected_rows
cols_ok = df.shape[1] == 2

print(f"   Expected labels (ham, spam): {'PASS' if labels_ok else 'FAIL'} (actual: {actual_labels})")
print(f"   Expected ~5574 rows        : {'PASS' if rows_ok else 'FAIL'} (actual: {len(df)})")
print(f"   Expected 2 columns         : {'PASS' if cols_ok else 'FAIL'} (actual: {df.shape[1]})")
print(f"   Tab-separated format       : PASS (loaded successfully)")

if labels_ok and rows_ok and cols_ok:
    print(f"   >>> Dataset matches UCI SMS Spam Collection v1 structure.")
else:
    print(f"   >>> Dataset does NOT fully match expected UCI SMS Spam Collection v1 structure.")

print(f"\n{SEPARATOR}")
print("AUDIT COMPLETE")
print(SEPARATOR)
