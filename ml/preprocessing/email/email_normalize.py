import pandas as pd
import os
import re
from sklearn.model_selection import train_test_split
import json

base_dir = r"c:\Users\Digit\Desktop\CyberNexus"
data_dir = os.path.join(base_dir, "data", "email")
out_dir = os.path.join(data_dir, "processed")

sources = [
    "CEAS_08.csv", "Enron.csv", "Ling.csv", 
    "Nazario.csv", "Nigerian_Fraud.csv", "SpamAssasin.csv"
]

def load_csv(path):
    try:
        return pd.read_csv(path, low_memory=False, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, low_memory=False, encoding='latin-1')
        except:
            return pd.read_csv(path, low_memory=False, encoding='cp1252')

dfs = []
source_counts = {}

print("Loading sources...")
for s in sources:
    path = os.path.join(data_dir, s)
    df = load_csv(path)
    df.columns = [c.lower().strip() for c in df.columns]
    
    for col in ['subject', 'body', 'sender', 'receiver', 'date', 'urls', 'label']:
        if col not in df.columns:
            df[col] = pd.NA
            
    source_name = s.replace('.csv', '')
    df['source'] = source_name
    
    # Keep original label, verify mapping
    df['original_label'] = df['label']
    
    df = df[['source', 'original_label', 'label', 'subject', 'body', 'sender', 'receiver', 'date', 'urls']]
    dfs.append(df)
    source_counts[source_name] = len(df)

combined = pd.concat(dfs, ignore_index=True)
initial_count = len(combined)

# Filtering specific Nazario artifact
nazario_mask = (combined['source'] == 'Nazario') & (combined['body'].fillna('').str.len() > 4000000)
artifact_removed = nazario_mask.sum()
combined = combined[~nazario_mask].copy()

# Handle missing subject/body and combine text
combined['subject'] = combined['subject'].fillna('').astype(str).str.strip()
combined['body'] = combined['body'].fillna('').astype(str).str.strip()
combined['subject'] = combined['subject'].replace('<NA>', '')
combined['body'] = combined['body'].replace('<NA>', '')

combined['text'] = combined.apply(lambda row: f"{row['subject']}\n{row['body']}".strip(), axis=1)

# Remove if both are totally empty
empty_mask = combined['text'] == ''
empty_removed = empty_mask.sum()
combined = combined[~empty_mask].copy()

# Deduplication across sources based on normalized text
print("Deduplicating...")
def norm_text(t):
    t = str(t).lower()
    t = re.sub(r'\s+', ' ', t)
    return t.strip()
    
combined['norm_text_for_dedup'] = combined['text'].apply(norm_text)
dupe_count = combined.duplicated(subset=['norm_text_for_dedup']).sum()
combined_clean = combined.drop_duplicates(subset=['norm_text_for_dedup'], keep='first').copy()
combined_clean.drop(columns=['norm_text_for_dedup'], inplace=True)

final_count = len(combined_clean)
legit_count = (combined_clean['label'] == 0).sum()
spam_count = (combined_clean['label'] == 1).sum()

print("Splitting datasets...")
# Splits (70/15/15)
train, temp = train_test_split(combined_clean, test_size=0.30, stratify=combined_clean['label'], random_state=42)
val, test = train_test_split(temp, test_size=0.50, stratify=temp['label'], random_state=42)

# Verify leakage
def verify_leakage(train, val, test, key='text'):
    train_set = set(train[key])
    val_set = set(val[key])
    test_set = set(test[key])
    assert len(train_set.intersection(val_set)) == 0, "Leakage: Train and Val"
    assert len(train_set.intersection(test_set)) == 0, "Leakage: Train and Test"
    assert len(val_set.intersection(test_set)) == 0, "Leakage: Val and Test"

# verify_leakage(train, val, test) # Text might not be perfectly unique if there are collisions, but wait, we deduplicated on norm_text_for_dedup. Text is the raw string, there might be slight variations. Let's verify on norm_text instead.
train_norm = set(train['text'].apply(norm_text))
val_norm = set(val['text'].apply(norm_text))
test_norm = set(test['text'].apply(norm_text))
assert len(train_norm.intersection(val_norm)) == 0, "Leakage: Train and Val"
assert len(train_norm.intersection(test_norm)) == 0, "Leakage: Train and Test"
assert len(val_norm.intersection(test_norm)) == 0, "Leakage: Val and Test"

print("Saving outputs...")
combined_clean.to_csv(os.path.join(out_dir, "email_clean.csv"), index=False)
train.to_csv(os.path.join(out_dir, "email_train.csv"), index=False)
val.to_csv(os.path.join(out_dir, "email_val.csv"), index=False)
test.to_csv(os.path.join(out_dir, "email_test.csv"), index=False)

source_dist = combined_clean['source'].value_counts().to_dict()

report = {
    "channel": "Email",
    "initial_rows": initial_count,
    "artifact_removed": int(artifact_removed),
    "empty_removed": int(empty_removed),
    "duplicates_removed": int(dupe_count),
    "final_rows": final_count,
    "legit_count": int(legit_count),
    "spam_count": int(spam_count),
    "source_distribution": source_dist,
    "train_rows": len(train),
    "val_rows": len(val),
    "test_rows": len(test)
}

with open(os.path.join(out_dir, "email_report.json"), "w") as f:
    json.dump(report, f, indent=4)

print("Email Normalization Complete")
print(json.dumps(report, indent=2))
