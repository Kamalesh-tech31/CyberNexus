import pandas as pd
import os
from sklearn.model_selection import train_test_split
import json

base_dir = r"c:\Users\Digit\Desktop\CyberNexus"
data_dir = os.path.join(base_dir, "data", "sms")
out_dir = os.path.join(data_dir, "processed")

input_file = os.path.join(data_dir, "SMSSpamCollection")

# Read data
df = pd.read_csv(input_file, sep='\t', header=None, names=['original_label', 'message'])
initial_count = len(df)

# Normalize labels
df['label'] = df['original_label'].map({'ham': 0, 'spam': 1})

# Safe text normalization (strip whitespace) BEFORE deduplication
df['message'] = df['message'].astype(str).str.strip()

# Check duplicates
dupe_count = df.duplicated(subset=['message']).sum()
df_clean = df.drop_duplicates(subset=['message'], keep='first').copy()

# Filter empty
empty_count = (df_clean['message'] == '').sum()
df_clean = df_clean[df_clean['message'] != '']

final_count = len(df_clean)
ham_count = (df_clean['label'] == 0).sum()
spam_count = (df_clean['label'] == 1).sum()

# Split (70/15/15)
train, temp = train_test_split(df_clean, test_size=0.30, stratify=df_clean['label'], random_state=42)
val, test = train_test_split(temp, test_size=0.50, stratify=temp['label'], random_state=42)

# Verify leakage
def verify_leakage(train, val, test, key='message'):
    train_set = set(train[key])
    val_set = set(val[key])
    test_set = set(test[key])
    assert len(train_set.intersection(val_set)) == 0, "Leakage: Train and Val"
    assert len(train_set.intersection(test_set)) == 0, "Leakage: Train and Test"
    assert len(val_set.intersection(test_set)) == 0, "Leakage: Val and Test"

verify_leakage(train, val, test)

# Save
df_clean.to_csv(os.path.join(out_dir, "sms_clean.csv"), index=False)
train.to_csv(os.path.join(out_dir, "sms_train.csv"), index=False)
val.to_csv(os.path.join(out_dir, "sms_val.csv"), index=False)
test.to_csv(os.path.join(out_dir, "sms_test.csv"), index=False)

report = {
    "channel": "SMS",
    "initial_rows": initial_count,
    "duplicates_removed": int(dupe_count),
    "empty_removed": int(empty_count),
    "final_rows": final_count,
    "ham_count": int(ham_count),
    "spam_count": int(spam_count),
    "train_rows": len(train),
    "val_rows": len(val),
    "test_rows": len(test)
}

with open(os.path.join(out_dir, "sms_report.json"), "w") as f:
    json.dump(report, f, indent=4)
    
print("SMS Normalization Complete")
print(json.dumps(report, indent=2))
