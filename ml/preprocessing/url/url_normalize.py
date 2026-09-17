import pandas as pd
import os
from sklearn.model_selection import train_test_split
import json

base_dir = r"c:\Users\Digit\Desktop\CyberNexus"
data_dir = os.path.join(base_dir, "data", "url")
out_dir = os.path.join(data_dir, "processed")

input_file = os.path.join(data_dir, "phishing_site_urls.csv")

df = pd.read_csv(input_file, low_memory=False)
initial_count = len(df)

df.rename(columns={'URL': 'url', 'Label': 'original_label'}, inplace=True)
df['label'] = df['original_label'].map({'good': 0, 'bad': 1})

# Filtering rules
def is_valid_url(x):
    s = str(x).strip()
    if len(s) < 5: return False
    if any(ord(c) < 32 or ord(c) == 127 for c in s): # Unprintable chars
        return False
    # Explicitly catch the garbled bytes noted in audit
    if '\x87' in s or '½\x134+' in s or 'ºE' in s:
        return False
    return True

valid_mask = df['url'].apply(is_valid_url)
invalid_count = (~valid_mask).sum()
df_valid = df[valid_mask].copy()

# Deduplicate
dupe_count = df_valid.duplicated(subset=['url']).sum()
df_clean = df_valid.drop_duplicates(subset=['url'], keep='first').copy()

cleaned_total = len(df_clean)

# Sample 100k
if cleaned_total > 100000:
    df_sample, _ = train_test_split(df_clean, train_size=100000, stratify=df_clean['label'], random_state=42)
else:
    df_sample = df_clean.copy()

sampled_total = len(df_sample)
good_count = (df_sample['label'] == 0).sum()
bad_count = (df_sample['label'] == 1).sum()

# Splits (70/15/15)
train, temp = train_test_split(df_sample, test_size=0.30, stratify=df_sample['label'], random_state=42)
val, test = train_test_split(temp, test_size=0.50, stratify=temp['label'], random_state=42)

# Verify leakage
def verify_leakage(train, val, test, key='url'):
    train_set = set(train[key])
    val_set = set(val[key])
    test_set = set(test[key])
    assert len(train_set.intersection(val_set)) == 0, "Leakage: Train and Val"
    assert len(train_set.intersection(test_set)) == 0, "Leakage: Train and Test"
    assert len(val_set.intersection(test_set)) == 0, "Leakage: Val and Test"

verify_leakage(train, val, test)

# Save
df_clean.to_csv(os.path.join(out_dir, "url_clean_full.csv"), index=False)
df_sample.to_csv(os.path.join(out_dir, "url_clean_sample.csv"), index=False)
train.to_csv(os.path.join(out_dir, "url_train.csv"), index=False)
val.to_csv(os.path.join(out_dir, "url_val.csv"), index=False)
test.to_csv(os.path.join(out_dir, "url_test.csv"), index=False)

report = {
    "channel": "URL",
    "initial_rows": initial_count,
    "invalid_removed": int(invalid_count),
    "duplicates_removed": int(dupe_count),
    "cleaned_total": cleaned_total,
    "sampled_total": sampled_total,
    "good_count": int(good_count),
    "bad_count": int(bad_count),
    "train_rows": len(train),
    "val_rows": len(val),
    "test_rows": len(test)
}

with open(os.path.join(out_dir, "url_report.json"), "w") as f:
    json.dump(report, f, indent=4)
    
print("URL Normalization Complete")
print(json.dumps(report, indent=2))
