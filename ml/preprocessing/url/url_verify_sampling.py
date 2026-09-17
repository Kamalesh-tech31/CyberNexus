import pandas as pd
import os
from sklearn.model_selection import train_test_split
import json

base_dir = r"c:\Users\Digit\Desktop\CyberNexus"
data_dir = os.path.join(base_dir, "data", "url")
out_dir = os.path.join(data_dir, "processed")

# Load existing clean full dataset instead of repeating everything
df_clean = pd.read_csv(os.path.join(out_dir, "url_clean_full.csv"), low_memory=False)

cleaned_total = len(df_clean)
clean_counts = df_clean['label'].value_counts()
clean_good = clean_counts.get(0, 0)
clean_bad = clean_counts.get(1, 0)

print("### Before sampling (Cleaned Dataset)")
print(f"* total rows: {cleaned_total}")
print(f"* Good count: {clean_good}")
print(f"* Bad count: {clean_bad}")
print(f"* percentages: Good: {clean_good/cleaned_total*100:.4f}%, Bad: {clean_bad/cleaned_total*100:.4f}%")

# Sample 100k
df_sample, _ = train_test_split(df_clean, train_size=100000, stratify=df_clean['label'], random_state=42)

sampled_total = len(df_sample)
sample_counts = df_sample['label'].value_counts()
sample_good = sample_counts.get(0, 0)
sample_bad = sample_counts.get(1, 0)

print("\n### After sampling (100k Sample)")
print(f"* total rows: {sampled_total}")
print(f"* Good count: {sample_good}")
print(f"* Bad count: {sample_bad}")
print(f"* percentages: Good: {sample_good/sampled_total*100:.4f}%, Bad: {sample_bad/sampled_total*100:.4f}%")
print(f"* percentage-point difference from the cleaned dataset: Good: {(sample_good/sampled_total*100) - (clean_good/cleaned_total*100):.6f}, Bad: {(sample_bad/sampled_total*100) - (clean_bad/cleaned_total*100):.6f}")

# Splits (70/15/15)
train, temp = train_test_split(df_sample, test_size=0.30, stratify=df_sample['label'], random_state=42)
val, test = train_test_split(temp, test_size=0.50, stratify=temp['label'], random_state=42)

print("\n### Splits")
print(f"* train rows: {len(train)}")
print(f"* validation rows: {len(val)}")
print(f"* test rows: {len(test)}")

def get_dist(df):
    c = df['label'].value_counts(normalize=True)*100
    return f"Good: {c.get(0,0):.4f}%, Bad: {c.get(1,0):.4f}%"

print(f"* class distribution in train: {get_dist(train)}")
print(f"* class distribution in val: {get_dist(val)}")
print(f"* class distribution in test: {get_dist(test)}")

print("\n### Leakage")
train_urls = set(train['url'])
val_urls = set(val['url'])
test_urls = set(test['url'])
print(f"* train/validation intersection: {len(train_urls.intersection(val_urls))}")
print(f"* train/test intersection: {len(train_urls.intersection(test_urls))}")
print(f"* validation/test intersection: {len(val_urls.intersection(test_urls))}")

# Re-save
df_sample.to_csv(os.path.join(out_dir, "url_clean_sample.csv"), index=False)
train.to_csv(os.path.join(out_dir, "url_train.csv"), index=False)
val.to_csv(os.path.join(out_dir, "url_val.csv"), index=False)
test.to_csv(os.path.join(out_dir, "url_test.csv"), index=False)

# Update report
with open(os.path.join(out_dir, "url_report.json"), "r") as f:
    report = json.load(f)

with open(os.path.join(out_dir, "url_report.json"), "w") as f:
    json.dump(report, f, indent=4)
