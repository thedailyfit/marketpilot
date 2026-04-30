"""
ML Model Training Pipeline
Trains XGBoost classifier to predict trade outcomes.
"""
import os
import json
import pickle
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# Try importing XGBoost, fallback to simple model if not available
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from ml.feature_engineer import extract_features, get_feature_names, features_to_array


MODEL_PATH = "ml/models/win_predictor.pkl"
TRAINING_DATA_PATH = "ml/training_data.json"


class SimplePredictor:
    """
    Fallback predictor using rule-based heuristics.
    Used when XGBoost is not available.
    """
    def __init__(self):
        self.thresholds = {
            'rsi_bullish': 35,
            'rsi_bearish': 65,
            'trend_weight': 0.3,
            'volume_weight': 0.2
        }
    
    def predict_proba(self, features: List[List[float]]) -> List[List[float]]:
        """Return [prob_loss, prob_win] for each sample."""
        results = []
        for f in features:
            # Simple heuristic based on key features
            feature_dict = dict(zip(get_feature_names(), f))
            
            score = 0.5  # Base probability
            
            # RSI contribution
            rsi = feature_dict.get('rsi_14', 50)
            if rsi < 35:
                score += 0.1  # Oversold = bullish
            elif rsi > 65:
                score += 0.1  # Overbought = bearish (if shorting)
            
            # Trend contribution
            if feature_dict.get('trend_up', 0) > 0:
                score += 0.1
            if feature_dict.get('trend_strength', 0) > 0.5:
                score += 0.05
            
            # Volume contribution
            if feature_dict.get('volume_ratio', 1) > 1.2:
                score += 0.05
            
            # ADX contribution (trending markets are easier)
            if feature_dict.get('adx', 20) > 25:
                score += 0.05
            
            # Time penalty (afternoon is volatile)
            if feature_dict.get('is_afternoon', 0) > 0:
                score -= 0.05
            
            # Friday penalty
            if feature_dict.get('is_friday', 0) > 0:
                score -= 0.03
            
            score = max(0.1, min(0.9, score))  # Clamp
            results.append([1 - score, score])
        
        return results
    
    def fit(self, X, y):
        """No-op for simple predictor."""
        pass


def load_training_data() -> List[Dict]:
    """Load labeled training data from file."""
    if not os.path.exists(TRAINING_DATA_PATH):
        return []
    
    with open(TRAINING_DATA_PATH, 'r') as f:
        return json.load(f)


def save_training_data(data: List[Dict]):
    """Save training data to file."""
    os.makedirs(os.path.dirname(TRAINING_DATA_PATH), exist_ok=True)
    with open(TRAINING_DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def add_training_sample(
    features: Dict[str, float],
    outcome: int,  # 1 = win, 0 = loss
    direction: str,
    pnl: float
):
    """Add a new training sample after trade closes."""
    data = load_training_data()
    
    sample = {
        "timestamp": datetime.now().isoformat(),
        "features": features,
        "outcome": outcome,
        "direction": direction,
        "pnl": pnl
    }
    
    data.append(sample)
    save_training_data(data)
    
    print(f"Training sample added. Total samples: {len(data)}")


def prepare_training_data(data: List[Dict]) -> Tuple[List[List[float]], List[int]]:
    """Convert training data to X, y format."""
    X = []
    y = []
    
    feature_names = get_feature_names()
    
    for sample in data:
        features = sample.get('features', {})
        feature_array = [features.get(name, 0.0) for name in feature_names]
        X.append(feature_array)
        y.append(sample.get('outcome', 0))
    
    return X, y


def train_model(min_samples: int = 50) -> Optional[object]:
    """
    Train XGBoost model on collected data.
    
    Args:
        min_samples: Minimum samples required for training
    
    Returns:
        Trained model or None if not enough data
    """
    data = load_training_data()
    
    if len(data) < min_samples:
        print(f"Not enough training data. Have {len(data)}, need {min_samples}.")
        return None
    
    X, y = prepare_training_data(data)
    
    if HAS_XGBOOST and HAS_NUMPY:
        print("Training XGBoost classifier...")
        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            objective='binary:logistic',
            eval_metric='logloss',
            use_label_encoder=False
        )
        
        X_np = np.array(X)
        y_np = np.array(y)
        
        model.fit(X_np, y_np)
        
        # Calculate training accuracy
        predictions = model.predict(X_np)
        accuracy = sum(p == a for p, a in zip(predictions, y_np)) / len(y_np)
        print(f"Training accuracy: {accuracy:.2%}")
        
    else:
        print("XGBoost not available. Using SimplePredictor.")
        model = SimplePredictor()
        model.fit(X, y)
    
    # Save model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"Model saved to {MODEL_PATH}")
    return model


def load_model():
    """Load trained model from disk."""
    if not os.path.exists(MODEL_PATH):
        print("No trained model found. Using SimplePredictor.")
        return SimplePredictor()
    
    try:
        with open(MODEL_PATH, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Error loading model: {e}. Using SimplePredictor.")
        return SimplePredictor()


def predict_win_probability(
    candles: List[dict],
    prices: List[float],
    current_volume: float = 0.0,
    timestamp: float = 0.0
) -> float:
    """
    Predict probability of a winning trade.
    
    Returns:
        Float between 0 and 1 representing win probability
    """
    # Extract features
    features = extract_features(candles, prices, current_volume, timestamp)
    feature_array = features_to_array(features)
    
    # Load model
    model = load_model()
    
    # Predict
    probas = model.predict_proba([feature_array])
    
    # Return probability of class 1 (win)
    return round(probas[0][1], 2)


if __name__ == "__main__":
    # Command-line training
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "train":
        min_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        train_model(min_samples)
    else:
        print("Usage: python train_model.py train [min_samples]")
        print(f"Current training samples: {len(load_training_data())}")
