"""
CyberNexus - Phase 4: Two-Model Training & Controlled Comparison

This script trains and compares EXACTLY TWO candidate algorithms per channel:
1. Logistic Regression (Linear Baseline)
2. LightGBM (Gradient-Boosted Decision Trees)

Channels:
- SMS (Independent)
- Email (Independent)
- URL (Independent)

Rules:
- Validation-based hyperparameter tuning using positive class F1.
- Frozen candidate models evaluated on held-out test sets.
- Meaningful difference rule: |ΔF1| < 0.01 indicates a tie, preferring simpler model (LR) unless strong secondary metric advantage.
- All models, metrics, and confusion matrices saved to ml/models/ and ml/evaluation/.
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix
)
import lightgbm as lgb

# Ensure UTF-8 output encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def compute_metrics(y_true, y_pred, y_prob):
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
            "matrix": [[int(tn), int(fp)], [int(fn), int(tp)]]
        }
    }


# ==============================================================================
# 1. SMS TRAINING & COMPARISON
# ==============================================================================
def train_sms(base_dir: str):
    print("\n" + "=" * 70)
    print("CHANNEL 1: SMS (Two-Model Training & Comparison)")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "sms", "processed", "features")
    models_dir = os.path.join(base_dir, "ml", "models", "sms")
    
    # Load features
    X_train = sparse.load_npz(os.path.join(data_dir, "sms_X_train.npz"))
    X_val = sparse.load_npz(os.path.join(data_dir, "sms_X_val.npz"))
    X_test = sparse.load_npz(os.path.join(data_dir, "sms_X_test.npz"))
    
    y_train = np.load(os.path.join(data_dir, "sms_y_train.npy"))
    y_val = np.load(os.path.join(data_dir, "sms_y_val.npy"))
    y_test = np.load(os.path.join(data_dir, "sms_y_test.npy"))
    
    print(f"SMS Data Shapes: Train={X_train.shape}, Val={X_val.shape}, Test={X_test.shape}")
    print(f"SMS Class Counts (Train): Ham (0)={(y_train==0).sum()}, Spam (1)={(y_train==1).sum()}")
    
    # --- Logistic Regression Tuning ---
    print("\n[SMS] Tuning Logistic Regression on Validation set...")
    lr_configs = [
        {"C": 0.1, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 1.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 5.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 10.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 1.0, "class_weight": "balanced", "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 5.0, "class_weight": "balanced", "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
    ]
    
    best_lr_model = None
    best_lr_cfg = None
    best_lr_val_f1 = -1.0
    lr_tuning_results = []
    
    for cfg in lr_configs:
        clf = LogisticRegression(**cfg)
        t0 = time.time()
        clf.fit(X_train, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val)[:, 1]
        val_preds = clf.predict(X_val)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lr_tuning_results.append({
            "config": cfg,
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LR C={cfg['C']}, weight={cfg['class_weight']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f}")
        
        if val_metrics['f1'] > best_lr_val_f1:
            best_lr_val_f1 = val_metrics['f1']
            best_lr_model = clf
            best_lr_cfg = cfg
            
    print(f"  --> Best LR Configuration: {best_lr_cfg} with Val F1 = {best_lr_val_f1:.4f}")
    
    # --- LightGBM Tuning ---
    print("\n[SMS] Tuning LightGBM on Validation set...")
    X_train_lgb = X_train.astype(np.float32)
    X_val_lgb = X_val.astype(np.float32)
    X_test_lgb = X_test.astype(np.float32)
    
    lgb_configs = [
        {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 150, "learning_rate": 0.1, "num_leaves": 15, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "class_weight": "balanced", "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31, "class_weight": "balanced", "random_state": 42, "n_jobs": -1, "verbose": -1},
    ]
    
    best_lgb_model = None
    best_lgb_cfg = None
    best_lgb_val_f1 = -1.0
    lgb_tuning_results = []
    
    for cfg in lgb_configs:
        clf = lgb.LGBMClassifier(**cfg)
        t0 = time.time()
        clf.fit(X_train_lgb, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val_lgb)[:, 1]
        val_preds = clf.predict(X_val_lgb)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lgb_tuning_results.append({
            "config": {k: v for k, v in cfg.items() if k not in ['verbose', 'n_jobs']},
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LGBM n_est={cfg['n_estimators']}, lr={cfg['learning_rate']}, leaves={cfg['num_leaves']}, weight={cfg['class_weight']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f}")
        
        if val_metrics['f1'] > best_lgb_val_f1:
            best_lgb_val_f1 = val_metrics['f1']
            best_lgb_model = clf
            best_lgb_cfg = cfg

    print(f"  --> Best LightGBM Configuration: {best_lgb_cfg} with Val F1 = {best_lgb_val_f1:.4f}")
    
    # --- Measure Training Times and Sizes ---
    t0 = time.time()
    best_lr_model.fit(X_train, y_train)
    lr_train_time = time.time() - t0
    
    t0 = time.time()
    lr_val_probs = best_lr_model.predict_proba(X_val)[:, 1]
    lr_val_preds = best_lr_model.predict(X_val)
    lr_val_inf_time = time.time() - t0
    lr_val_metrics = compute_metrics(y_val, lr_val_preds, lr_val_probs)
    
    t0 = time.time()
    lr_test_probs = best_lr_model.predict_proba(X_test)[:, 1]
    lr_test_preds = best_lr_model.predict(X_test)
    lr_test_inf_time = time.time() - t0
    lr_test_metrics = compute_metrics(y_test, lr_test_preds, lr_test_probs)
    
    t0 = time.time()
    best_lgb_model.fit(X_train_lgb, y_train)
    lgb_train_time = time.time() - t0
    
    t0 = time.time()
    lgb_val_probs = best_lgb_model.predict_proba(X_val_lgb)[:, 1]
    lgb_val_preds = best_lgb_model.predict(X_val_lgb)
    lgb_val_inf_time = time.time() - t0
    lgb_val_metrics = compute_metrics(y_val, lgb_val_preds, lgb_val_probs)
    
    t0 = time.time()
    lgb_test_probs = best_lgb_model.predict_proba(X_test_lgb)[:, 1]
    lgb_test_preds = best_lgb_model.predict(X_test_lgb)
    lgb_test_inf_time = time.time() - t0
    lgb_test_metrics = compute_metrics(y_test, lgb_test_preds, lgb_test_probs)
    
    # Save models
    lr_path = os.path.join(models_dir, "logistic_regression", "sms_logistic_regression.joblib")
    lgb_path = os.path.join(models_dir, "lightgbm", "sms_lightgbm.joblib")
    joblib.dump(best_lr_model, lr_path)
    joblib.dump(best_lgb_model, lgb_path)
    
    lr_size_kb = os.path.getsize(lr_path) / 1024.0
    lgb_size_kb = os.path.getsize(lgb_path) / 1024.0
    
    # Comparison and Winner selection on VALIDATION set
    delta_f1 = abs(lr_val_metrics['f1'] - lgb_val_metrics['f1'])
    is_f1_tied = delta_f1 < 0.01
    
    if is_f1_tied:
        if lr_val_metrics['f1'] >= lgb_val_metrics['f1']:
            winner = "Logistic Regression"
            winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01). Logistic Regression selected for superior interpretability, smaller model size ({lr_size_kb:.1f} KB vs {lgb_size_kb:.1f} KB), and faster training."
        else:
            if lgb_val_metrics['roc_auc'] > lr_val_metrics['roc_auc'] + 0.01 or lgb_val_metrics['recall'] > lr_val_metrics['recall'] + 0.02:
                winner = "LightGBM"
                winner_reason = f"Validation F1 is close (|dF1| = {delta_f1:.4f} < 0.01), but LightGBM provides a meaningful advantage in secondary metrics (ROC-AUC: {lgb_val_metrics['roc_auc']:.4f} vs {lr_val_metrics['roc_auc']:.4f}, Recall: {lgb_val_metrics['recall']:.4f} vs {lr_val_metrics['recall']:.4f})."
            else:
                winner = "Logistic Regression"
                winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01) with comparable secondary metrics. Logistic Regression preferred as the simpler, more interpretable linear baseline."
    else:
        winner = "Logistic Regression" if lr_val_metrics['f1'] > lgb_val_metrics['f1'] else "LightGBM"
        winner_reason = f"Decisive validation F1 advantage (|dF1| = {delta_f1:.4f} >= 0.01)."
        
    print(f"\n[SMS WINNER (Validation)]: {winner}")
    print(f"Reason: {winner_reason}")
    
    return {
        "channel": "SMS",
        "logistic_regression": {
            "best_config": best_lr_cfg,
            "tuning_results": lr_tuning_results,
            "train_time_sec": lr_train_time,
            "val_inf_time_sec": lr_val_inf_time,
            "test_inf_time_sec": lr_test_inf_time,
            "model_size_kb": lr_size_kb,
            "val_metrics": lr_val_metrics,
            "test_metrics": lr_test_metrics
        },
        "lightgbm": {
            "best_config": {k: v for k, v in best_lgb_cfg.items() if k not in ['verbose', 'n_jobs']},
            "tuning_results": lgb_tuning_results,
            "train_time_sec": lgb_train_time,
            "val_inf_time_sec": lgb_val_inf_time,
            "test_inf_time_sec": lgb_test_inf_time,
            "model_size_kb": lgb_size_kb,
            "val_metrics": lgb_val_metrics,
            "test_metrics": lgb_test_metrics
        },
        "comparison": {
            "val_delta_f1": float(delta_f1),
            "is_val_f1_tied": bool(is_f1_tied),
            "winner": winner,
            "winner_reason": winner_reason
        }
    }


# ==============================================================================
# 2. EMAIL TRAINING & COMPARISON
# ==============================================================================
def train_email(base_dir: str):
    print("\n" + "=" * 70)
    print("CHANNEL 2: EMAIL (Two-Model Training & Comparison)")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "email", "processed", "features")
    models_dir = os.path.join(base_dir, "ml", "models", "email")
    
    # Load features
    X_train = sparse.load_npz(os.path.join(data_dir, "email_X_train.npz"))
    X_val = sparse.load_npz(os.path.join(data_dir, "email_X_val.npz"))
    X_test = sparse.load_npz(os.path.join(data_dir, "email_X_test.npz"))
    
    y_train = np.load(os.path.join(data_dir, "email_y_train.npy"))
    y_val = np.load(os.path.join(data_dir, "email_y_val.npy"))
    y_test = np.load(os.path.join(data_dir, "email_y_test.npy"))
    
    print(f"Email Data Shapes: Train={X_train.shape}, Val={X_val.shape}, Test={X_test.shape}")
    print(f"Email Class Counts (Train): Legit (0)={(y_train==0).sum()}, Phishing (1)={(y_train==1).sum()}")
    
    # --- Logistic Regression Tuning ---
    print("\n[Email] Tuning Logistic Regression on Validation set...")
    lr_configs = [
        {"C": 0.1, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 1.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 5.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 10.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
    ]
    
    best_lr_model = None
    best_lr_cfg = None
    best_lr_val_f1 = -1.0
    lr_tuning_results = []
    
    for cfg in lr_configs:
        clf = LogisticRegression(**cfg)
        t0 = time.time()
        clf.fit(X_train, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val)[:, 1]
        val_preds = clf.predict(X_val)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lr_tuning_results.append({
            "config": cfg,
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LR C={cfg['C']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f} (Fit: {fit_time:.2f}s)")
        
        if val_metrics['f1'] > best_lr_val_f1:
            best_lr_val_f1 = val_metrics['f1']
            best_lr_model = clf
            best_lr_cfg = cfg
            
    print(f"  --> Best LR Configuration: {best_lr_cfg} with Val F1 = {best_lr_val_f1:.4f}")
    
    # --- LightGBM Tuning ---
    print("\n[Email] Tuning LightGBM on Validation set (sparse TF-IDF matrix)...")
    X_train_lgb = X_train.astype(np.float32)
    X_val_lgb = X_val.astype(np.float32)
    X_test_lgb = X_test.astype(np.float32)
    
    lgb_configs = [
        {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 150, "learning_rate": 0.1, "num_leaves": 63, "random_state": 42, "n_jobs": -1, "verbose": -1},
    ]
    
    best_lgb_model = None
    best_lgb_cfg = None
    best_lgb_val_f1 = -1.0
    lgb_tuning_results = []
    
    for cfg in lgb_configs:
        clf = lgb.LGBMClassifier(**cfg)
        t0 = time.time()
        clf.fit(X_train_lgb, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val_lgb)[:, 1]
        val_preds = clf.predict(X_val_lgb)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lgb_tuning_results.append({
            "config": {k: v for k, v in cfg.items() if k not in ['verbose', 'n_jobs']},
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LGBM n_est={cfg['n_estimators']}, lr={cfg['learning_rate']}, leaves={cfg['num_leaves']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f} (Fit: {fit_time:.2f}s)")
        
        if val_metrics['f1'] > best_lgb_val_f1:
            best_lgb_val_f1 = val_metrics['f1']
            best_lgb_model = clf
            best_lgb_cfg = cfg

    print(f"  --> Best LightGBM Configuration: {best_lgb_cfg} with Val F1 = {best_lgb_val_f1:.4f}")
    
    # --- Measure Training Times and Sizes ---
    t0 = time.time()
    best_lr_model.fit(X_train, y_train)
    lr_train_time = time.time() - t0
    
    t0 = time.time()
    lr_val_probs = best_lr_model.predict_proba(X_val)[:, 1]
    lr_val_preds = best_lr_model.predict(X_val)
    lr_val_inf_time = time.time() - t0
    lr_val_metrics = compute_metrics(y_val, lr_val_preds, lr_val_probs)
    
    t0 = time.time()
    lr_test_probs = best_lr_model.predict_proba(X_test)[:, 1]
    lr_test_preds = best_lr_model.predict(X_test)
    lr_test_inf_time = time.time() - t0
    lr_test_metrics = compute_metrics(y_test, lr_test_preds, lr_test_probs)
    
    t0 = time.time()
    best_lgb_model.fit(X_train_lgb, y_train)
    lgb_train_time = time.time() - t0
    
    t0 = time.time()
    lgb_val_probs = best_lgb_model.predict_proba(X_val_lgb)[:, 1]
    lgb_val_preds = best_lgb_model.predict(X_val_lgb)
    lgb_val_inf_time = time.time() - t0
    lgb_val_metrics = compute_metrics(y_val, lgb_val_preds, lgb_val_probs)
    
    t0 = time.time()
    lgb_test_probs = best_lgb_model.predict_proba(X_test_lgb)[:, 1]
    lgb_test_preds = best_lgb_model.predict(X_test_lgb)
    lgb_test_inf_time = time.time() - t0
    lgb_test_metrics = compute_metrics(y_test, lgb_test_preds, lgb_test_probs)
    
    # Save models
    lr_path = os.path.join(models_dir, "logistic_regression", "email_logistic_regression.joblib")
    lgb_path = os.path.join(models_dir, "lightgbm", "email_lightgbm.joblib")
    joblib.dump(best_lr_model, lr_path)
    joblib.dump(best_lgb_model, lgb_path)
    
    lr_size_kb = os.path.getsize(lr_path) / 1024.0
    lgb_size_kb = os.path.getsize(lgb_path) / 1024.0
    
    # Comparison and Winner selection on VALIDATION set
    delta_f1 = abs(lr_val_metrics['f1'] - lgb_val_metrics['f1'])
    is_f1_tied = delta_f1 < 0.01
    
    if is_f1_tied:
        if lr_val_metrics['f1'] >= lgb_val_metrics['f1']:
            winner = "Logistic Regression"
            winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01). Logistic Regression chosen for superior interpretability, smaller model size ({lr_size_kb:.1f} KB vs {lgb_size_kb:.1f} KB), and faster training ({lr_train_time:.2f}s vs {lgb_train_time:.2f}s)."
        else:
            if lgb_val_metrics['roc_auc'] > lr_val_metrics['roc_auc'] + 0.01 or lgb_val_metrics['recall'] > lr_val_metrics['recall'] + 0.02:
                winner = "LightGBM"
                winner_reason = f"Validation F1 is close (|dF1| = {delta_f1:.4f} < 0.01), but LightGBM provides a meaningful secondary metric advantage (ROC-AUC: {lgb_val_metrics['roc_auc']:.4f} vs {lr_val_metrics['roc_auc']:.4f})."
            else:
                winner = "Logistic Regression"
                winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01) with comparable secondary metrics. Logistic Regression preferred as the simpler, more interpretable linear baseline."
    else:
        winner = "Logistic Regression" if lr_val_metrics['f1'] > lgb_val_metrics['f1'] else "LightGBM"
        winner_reason = f"Decisive validation F1 advantage (|dF1| = {delta_f1:.4f} >= 0.01)."
        
    print(f"\n[EMAIL WINNER (Validation)]: {winner}")
    print(f"Reason: {winner_reason}")
    
    return {
        "channel": "Email",
        "logistic_regression": {
            "best_config": best_lr_cfg,
            "tuning_results": lr_tuning_results,
            "train_time_sec": lr_train_time,
            "val_inf_time_sec": lr_val_inf_time,
            "test_inf_time_sec": lr_test_inf_time,
            "model_size_kb": lr_size_kb,
            "val_metrics": lr_val_metrics,
            "test_metrics": lr_test_metrics
        },
        "lightgbm": {
            "best_config": {k: v for k, v in best_lgb_cfg.items() if k not in ['verbose', 'n_jobs']},
            "tuning_results": lgb_tuning_results,
            "train_time_sec": lgb_train_time,
            "val_inf_time_sec": lgb_val_inf_time,
            "test_inf_time_sec": lgb_test_inf_time,
            "model_size_kb": lgb_size_kb,
            "val_metrics": lgb_val_metrics,
            "test_metrics": lgb_test_metrics
        },
        "comparison": {
            "val_delta_f1": float(delta_f1),
            "is_val_f1_tied": bool(is_f1_tied),
            "winner": winner,
            "winner_reason": winner_reason
        }
    }


# ==============================================================================
# 3. URL TRAINING & COMPARISON
# ==============================================================================
def train_url(base_dir: str):
    print("\n" + "=" * 70)
    print("CHANNEL 3: URL (Two-Model Training & Comparison)")
    print("=" * 70)
    
    data_dir = os.path.join(base_dir, "data", "url", "processed", "features")
    models_dir = os.path.join(base_dir, "ml", "models", "url")
    
    # Load scaled data (for LR) and unscaled data (for LightGBM)
    X_train_scaled = pd.read_csv(os.path.join(data_dir, "url_X_train_scaled.csv"))
    X_val_scaled = pd.read_csv(os.path.join(data_dir, "url_X_val_scaled.csv"))
    X_test_scaled = pd.read_csv(os.path.join(data_dir, "url_X_test_scaled.csv"))
    
    X_train_unscaled = pd.read_csv(os.path.join(data_dir, "url_X_train_unscaled.csv"))
    X_val_unscaled = pd.read_csv(os.path.join(data_dir, "url_X_val_unscaled.csv"))
    X_test_unscaled = pd.read_csv(os.path.join(data_dir, "url_X_test_unscaled.csv"))
    
    y_train = np.load(os.path.join(data_dir, "url_y_train.npy"))
    y_val = np.load(os.path.join(data_dir, "url_y_val.npy"))
    y_test = np.load(os.path.join(data_dir, "url_y_test.npy"))
    
    print(f"URL Data Shapes: Train={X_train_scaled.shape}, Val={X_val_scaled.shape}, Test={X_test_scaled.shape}")
    print(f"URL Class Counts (Train): Good (0)={(y_train==0).sum()}, Bad (1)={(y_train==1).sum()}")
    
    # --- Logistic Regression Tuning ---
    print("\n[URL] Tuning Logistic Regression on Validation set...")
    lr_configs = [
        {"C": 0.01, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 0.1, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 1.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 10.0, "class_weight": None, "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 1.0, "class_weight": "balanced", "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
        {"C": 10.0, "class_weight": "balanced", "solver": "lbfgs", "max_iter": 1000, "random_state": 42},
    ]
    
    best_lr_model = None
    best_lr_cfg = None
    best_lr_val_f1 = -1.0
    lr_tuning_results = []
    
    for cfg in lr_configs:
        clf = LogisticRegression(**cfg)
        t0 = time.time()
        clf.fit(X_train_scaled, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val_scaled)[:, 1]
        val_preds = clf.predict(X_val_scaled)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lr_tuning_results.append({
            "config": cfg,
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LR C={cfg['C']}, weight={cfg['class_weight']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f}")
        
        if val_metrics['f1'] > best_lr_val_f1:
            best_lr_val_f1 = val_metrics['f1']
            best_lr_model = clf
            best_lr_cfg = cfg
            
    print(f"  --> Best LR Configuration: {best_lr_cfg} with Val F1 = {best_lr_val_f1:.4f}")
    
    # --- LightGBM Tuning ---
    print("\n[URL] Tuning LightGBM on Validation set (15 structural features)...")
    lgb_configs = [
        {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.1, "num_leaves": 63, "class_weight": None, "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "class_weight": "balanced", "random_state": 42, "n_jobs": -1, "verbose": -1},
        {"n_estimators": 200, "learning_rate": 0.05, "num_leaves": 63, "class_weight": "balanced", "random_state": 42, "n_jobs": -1, "verbose": -1},
    ]
    
    best_lgb_model = None
    best_lgb_cfg = None
    best_lgb_val_f1 = -1.0
    lgb_tuning_results = []
    
    for cfg in lgb_configs:
        clf = lgb.LGBMClassifier(**cfg)
        t0 = time.time()
        clf.fit(X_train_unscaled, y_train)
        fit_time = time.time() - t0
        
        val_probs = clf.predict_proba(X_val_unscaled)[:, 1]
        val_preds = clf.predict(X_val_unscaled)
        val_metrics = compute_metrics(y_val, val_preds, val_probs)
        
        lgb_tuning_results.append({
            "config": {k: v for k, v in cfg.items() if k not in ['verbose', 'n_jobs']},
            "val_metrics": val_metrics,
            "train_time": fit_time
        })
        print(f"  LGBM n_est={cfg['n_estimators']}, lr={cfg['learning_rate']}, leaves={cfg['num_leaves']}, weight={cfg['class_weight']} -> Val F1: {val_metrics['f1']:.4f}, Prec: {val_metrics['precision']:.4f}, Rec: {val_metrics['recall']:.4f}, ROC-AUC: {val_metrics['roc_auc']:.4f}")
        
        if val_metrics['f1'] > best_lgb_val_f1:
            best_lgb_val_f1 = val_metrics['f1']
            best_lgb_model = clf
            best_lgb_cfg = cfg

    print(f"  --> Best LightGBM Configuration: {best_lgb_cfg} with Val F1 = {best_lgb_val_f1:.4f}")
    
    # --- Measure Training Times and Sizes ---
    t0 = time.time()
    best_lr_model.fit(X_train_scaled, y_train)
    lr_train_time = time.time() - t0
    
    t0 = time.time()
    lr_val_probs = best_lr_model.predict_proba(X_val_scaled)[:, 1]
    lr_val_preds = best_lr_model.predict(X_val_scaled)
    lr_val_inf_time = time.time() - t0
    lr_val_metrics = compute_metrics(y_val, lr_val_preds, lr_val_probs)
    
    t0 = time.time()
    lr_test_probs = best_lr_model.predict_proba(X_test_scaled)[:, 1]
    lr_test_preds = best_lr_model.predict(X_test_scaled)
    lr_test_inf_time = time.time() - t0
    lr_test_metrics = compute_metrics(y_test, lr_test_preds, lr_test_probs)
    
    t0 = time.time()
    best_lgb_model.fit(X_train_unscaled, y_train)
    lgb_train_time = time.time() - t0
    
    t0 = time.time()
    lgb_val_probs = best_lgb_model.predict_proba(X_val_unscaled)[:, 1]
    lgb_val_preds = best_lgb_model.predict(X_val_unscaled)
    lgb_val_inf_time = time.time() - t0
    lgb_val_metrics = compute_metrics(y_val, lgb_val_preds, lgb_val_probs)
    
    t0 = time.time()
    lgb_test_probs = best_lgb_model.predict_proba(X_test_unscaled)[:, 1]
    lgb_test_preds = best_lgb_model.predict(X_test_unscaled)
    lgb_test_inf_time = time.time() - t0
    lgb_test_metrics = compute_metrics(y_test, lgb_test_preds, lgb_test_probs)
    
    # Save models
    lr_path = os.path.join(models_dir, "logistic_regression", "url_logistic_regression.joblib")
    lgb_path = os.path.join(models_dir, "lightgbm", "url_lightgbm.joblib")
    joblib.dump(best_lr_model, lr_path)
    joblib.dump(best_lgb_model, lgb_path)
    
    lr_size_kb = os.path.getsize(lr_path) / 1024.0
    lgb_size_kb = os.path.getsize(lgb_path) / 1024.0
    
    # Comparison and Winner selection on VALIDATION set
    delta_f1 = abs(lr_val_metrics['f1'] - lgb_val_metrics['f1'])
    is_f1_tied = delta_f1 < 0.01
    
    if is_f1_tied:
        if lr_val_metrics['f1'] >= lgb_val_metrics['f1']:
            winner = "Logistic Regression"
            winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01). Logistic Regression chosen for simplicity and interpretability."
        else:
            if lgb_val_metrics['roc_auc'] > lr_val_metrics['roc_auc'] + 0.01 or lgb_val_metrics['recall'] > lr_val_metrics['recall'] + 0.02:
                winner = "LightGBM"
                winner_reason = f"Validation F1 is close (|dF1| = {delta_f1:.4f} < 0.01), but LightGBM provides a meaningful advantage in secondary metrics (ROC-AUC: {lgb_val_metrics['roc_auc']:.4f} vs {lr_val_metrics['roc_auc']:.4f}, Recall: {lgb_val_metrics['recall']:.4f} vs {lr_val_metrics['recall']:.4f})."
            else:
                winner = "Logistic Regression"
                winner_reason = f"Practically tied on validation F1 (|dF1| = {delta_f1:.4f} < 0.01) with comparable secondary metrics. Logistic Regression preferred as the simpler, more interpretable linear baseline."
    else:
        winner = "Logistic Regression" if lr_val_metrics['f1'] > lgb_val_metrics['f1'] else "LightGBM"
        winner_reason = f"Decisive validation F1 advantage (|dF1| = {delta_f1:.4f} >= 0.01)."
        
    print(f"\n[URL WINNER (Validation)]: {winner}")
    print(f"Reason: {winner_reason}")
    
    return {
        "channel": "URL",
        "logistic_regression": {
            "best_config": best_lr_cfg,
            "tuning_results": lr_tuning_results,
            "train_time_sec": lr_train_time,
            "val_inf_time_sec": lr_val_inf_time,
            "test_inf_time_sec": lr_test_inf_time,
            "model_size_kb": lr_size_kb,
            "val_metrics": lr_val_metrics,
            "test_metrics": lr_test_metrics
        },
        "lightgbm": {
            "best_config": {k: v for k, v in best_lgb_cfg.items() if k not in ['verbose', 'n_jobs']},
            "tuning_results": lgb_tuning_results,
            "train_time_sec": lgb_train_time,
            "val_inf_time_sec": lgb_val_inf_time,
            "test_inf_time_sec": lgb_test_inf_time,
            "model_size_kb": lgb_size_kb,
            "val_metrics": lgb_val_metrics,
            "test_metrics": lgb_test_metrics
        },
        "comparison": {
            "val_delta_f1": float(delta_f1),
            "is_val_f1_tied": bool(is_f1_tied),
            "winner": winner,
            "winner_reason": winner_reason
        }
    }


def main():
    base_dir = r"c:\Users\Digit\Desktop\CyberNexus"
    eval_dir = os.path.join(base_dir, "ml", "evaluation")
    os.makedirs(eval_dir, exist_ok=True)
    
    print("\n" + "#" * 70)
    print("STARTING CYBERNEXUS PHASE 4 TWO-MODEL TRAINING & COMPARISON")
    print("#" * 70)
    
    sms_results = train_sms(base_dir)
    email_results = train_email(base_dir)
    url_results = train_url(base_dir)
    
    full_report = {
        "phase": "Phase 4 - Two-Model Training & Controlled Comparison",
        "environment": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "scikit_learn_version": LogisticRegression.__module__,
            "lightgbm_version": lgb.__version__
        },
        "channels": {
            "sms": sms_results,
            "email": email_results,
            "url": url_results
        }
    }
    
    report_path = os.path.join(eval_dir, "phase4_model_comparison_results.json")
    with open(report_path, "w", encoding='utf-8') as f:
        json.dump(full_report, f, indent=4)
        
    print("\n" + "=" * 70)
    print(f"FULL PHASE 4 RESULTS SAVED TO: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
