"""Train + persist CPU-only models with versioned metadata. Run: `python -m app.ai.training`."""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ai import synthetic as syn
from app.core.config import settings

VERSION = "1.0.0"
SPECS = {  # name -> (algorithm label, feature list)
    "lead_conversion": ("logistic_regression", syn.LEAD_FEATURES),
    "customer_churn": ("random_forest", syn.CHURN_FEATURES),
    "project_delay": ("gradient_boosting", syn.PROJECT_FEATURES),
    "ticket_sentiment": ("tfidf_logistic_regression", ["text"]),
    "ticket_priority": ("tfidf_logistic_regression", ["text"]),
}


def model_dir() -> Path:
    p = Path(settings.model_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _binary_metrics(model, X_te, y_te):
    proba = model.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {"accuracy": accuracy_score(y_te, pred), "precision": precision_score(y_te, pred, zero_division=0),
            "recall": recall_score(y_te, pred, zero_division=0), "f1": f1_score(y_te, pred, zero_division=0),
            "roc_auc": roc_auc_score(y_te, proba), "test_size": int(len(y_te)), "positive_rate": float(np.mean(y_te))}


def _train_tabular(name, df, features, estimator):
    X, y = df[features], df["label"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    estimator.fit(X_tr, y_tr)
    metrics = _binary_metrics(estimator, X_te, y_te)
    # baseline (population means) used for local explanations
    baseline = X_tr.mean().to_dict()
    return estimator, metrics, {"baseline": baseline, "train_means": baseline}


def _train_text(df):
    X_tr, X_te, y_tr, y_te = train_test_split(df["text"], df["label"], test_size=0.25, random_state=42, stratify=df["label"])
    pipe = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True),
                         LogisticRegression(max_iter=1000, C=3.0))
    pipe.fit(X_tr, y_tr)
    pred = pipe.predict(X_te)
    labels = list(pipe.classes_)
    return pipe, {"accuracy": accuracy_score(y_te, pred), "precision_macro": precision_score(y_te, pred, average="macro"),
                  "recall_macro": recall_score(y_te, pred, average="macro"), "f1_macro": f1_score(y_te, pred, average="macro"),
                  "labels": labels, "confusion_matrix": confusion_matrix(y_te, pred, labels=labels).tolist(),
                  "test_size": int(len(y_te))}, {}


def train_one(name: str) -> dict:
    algo, features = SPECS[name]
    if name == "lead_conversion":
        est = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
        model, metrics, extra = _train_tabular(name, syn.lead_data(), features, est)
    elif name == "customer_churn":
        est = RandomForestClassifier(n_estimators=150, max_depth=8, min_samples_leaf=5, random_state=42, n_jobs=1)
        model, metrics, extra = _train_tabular(name, syn.churn_data(), features, est)
    elif name == "project_delay":
        est = GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=42)
        model, metrics, extra = _train_tabular(name, syn.project_data(), features, est)
    elif name == "ticket_sentiment":
        model, metrics, extra = _train_text(syn.sentiment_data())
    else:
        model, metrics, extra = _train_text(syn.priority_data())
    meta = {"name": name, "algorithm": algo, "version": VERSION, "features": features,
            "trained_at": datetime.now(timezone.utc).isoformat(), "training_data": "synthetic (Stage A)",
            "metrics": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()}, **extra}
    d = model_dir()
    joblib.dump(model, d / f"{name}.joblib")
    (d / f"{name}.json").write_text(json.dumps(meta, indent=2, default=float))
    return meta


def train_all() -> list[dict]:
    return [train_one(n) for n in SPECS]


if __name__ == "__main__":
    for m in train_all():
        print(m["name"], m["version"], json.dumps(m["metrics"]))
