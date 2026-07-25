"""
ML prediction pipeline for heart disease detection.
Pipeline: StandardScaler → PCA(0.95) → RandomForestClassifier
Features (in order): cp, oldpeak, ca, thalach, thal, exang
"""
import os
import warnings
import numpy as np
import joblib

_BASE = os.path.join(os.path.dirname(__file__), 'models')

# Lazy-loaded singletons
_scaler = None
_pca    = None
_model  = None


def _load():
    global _scaler, _pca, _model
    if _model is None:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _scaler = joblib.load(os.path.join(_BASE, 'scaler.pkl'))
            _pca    = joblib.load(os.path.join(_BASE, 'pca.pkl'))
            _model  = joblib.load(os.path.join(_BASE, 'heart_model.pkl'))


def predict(cp, oldpeak, ca, thalach, thal, exang):
    """
    Run the full ML pipeline for one patient record.

    Returns:
        prediction (int)  : 0 = No Disease, 1 = Heart Disease
        risk_score (float): 0–100, probability of disease × 100
        risk_level (str)  : 'Low' | 'Medium' | 'High'
    """
    _load()

    X        = np.array([[cp, oldpeak, ca, thalach, thal, exang]], dtype=float)
    X_scaled = _scaler.transform(X)
    X_pca    = _pca.transform(X_scaled)

    prob  = float(_model.predict_proba(X_pca)[0][1])
    pred  = int(_model.predict(X_pca)[0])
    score = round(prob * 100, 1)

    if prob >= 0.65:
        level = 'High'
    elif prob >= 0.35:
        level = 'Medium'
    else:
        level = 'Low'

    return pred, score, level
