"""LSTM model service: load models, predict slopes, fine-tune with new data.

Replicates the feature pipeline from train_crypto_slope_grid_search.py
so that inference and fine-tuning use the same preprocessing.
"""

import json
import logging
import os

import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.klines_fetcher import fetch_klines

logger = logging.getLogger(__name__)


def _model_dir(symbol: str, timeframe: str) -> str:
    return os.path.join(settings.LSTM_MODELS_DIR, symbol.upper(), timeframe)


def _load_meta(symbol: str, timeframe: str) -> dict | None:
    path = os.path.join(_model_dir(symbol, timeframe), "meta.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _load_model(symbol: str, timeframe: str):
    """Load a Keras model from disk. Returns (model, meta) or (None, None)."""
    import tensorflow as tf

    model_path = os.path.join(_model_dir(symbol, timeframe), "saved_model.keras")
    meta = _load_meta(symbol, timeframe)
    if meta is None or not os.path.exists(model_path):
        return None, None
    model = tf.keras.models.load_model(model_path)
    return model, meta


def _build_features(closes: np.ndarray, meta: dict) -> np.ndarray:
    """Build feature matrix from close prices, matching the training pipeline.

    Features (in order): close, ema6 (if USE_EMA_FAST), logret (if USE_LOGRET).
    Each feature is z-scored using the training statistics from meta.
    """
    params = meta["params"]
    feat_list = []

    # close
    feat_list.append(closes.copy())

    # ema fast
    if params.get("USE_EMA_FAST", True):
        ema = pd.Series(closes).ewm(span=6, adjust=False).mean().values.astype(np.float32)
        feat_list.append(ema)

    # log returns
    if params.get("USE_LOGRET", True):
        logret = np.zeros_like(closes, dtype=np.float32)
        base = np.clip(closes[:-1], 1e-8, 1e12)
        logret[1:] = np.log(np.clip(closes[1:] / base, 1e-8, 1e8)).astype(np.float32)
        feat_list.append(logret)

    # vol24
    if params.get("USE_VOL24", False):
        lr_idx = 2 if params.get("USE_EMA_FAST", True) else 1
        lr = feat_list[lr_idx] if params.get("USE_LOGRET", True) else np.zeros_like(closes)
        vol = pd.Series(lr).rolling(window=24, min_periods=1).std().values.astype(np.float32)
        feat_list.append(vol)

    Z = np.stack(feat_list, axis=-1).astype(np.float32)

    # z-score using training stats
    feat_mus = meta["feat_mus"]
    feat_sds = meta["feat_sds"]
    for j in range(Z.shape[-1]):
        mu = feat_mus[j]
        sd = feat_sds[j] if feat_sds[j] > 1e-12 else 1.0
        Z[:, j] = (Z[:, j] - mu) / sd

    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    return Z


def _build_slope_target(closes: np.ndarray, smooth_win: int) -> np.ndarray:
    """Build smoothed slope target from close prices."""
    slope_raw = np.empty_like(closes)
    slope_raw[:] = np.nan
    slope_raw[1:] = closes[1:] - closes[:-1]
    slope_raw[0] = slope_raw[1] if len(closes) > 1 else 0.0
    s = pd.Series(slope_raw).replace([np.inf, -np.inf], np.nan).interpolate().bfill().ffill()
    slope = s.ewm(span=smooth_win, adjust=False).mean().bfill().ffill().values.astype(np.float32)
    return slope


def has_model(symbol: str, timeframe: str) -> bool:
    meta = _load_meta(symbol, timeframe)
    return meta is not None


def predict_slope(symbol: str, timeframe: str) -> float | None:
    """Predict the next-candle slope for a symbol/timeframe.

    Fetches the latest klines, builds features, and runs inference.
    Returns the predicted slope value, or None if the model is not available.
    """
    model, meta = _load_model(symbol, timeframe)
    if model is None:
        return None

    window = meta["params"]["WINDOW"]

    # Fetch enough klines to fill the window + margin for feature computation
    klines = fetch_klines(symbol, interval=timeframe, limit=window + 50)
    if len(klines) < window:
        logger.warning(f"Not enough klines for {symbol}/{timeframe}: {len(klines)} < {window}")
        return None

    closes = np.array([k["close"] for k in klines], dtype=np.float32)
    Z = _build_features(closes, meta)

    # Take the last `window` candles as input
    X = Z[-window:][np.newaxis, :, :]  # shape (1, window, n_features)
    pred = float(model.predict(X, verbose=0)[0, 0])
    return pred


def predict_slopes(symbol: str, timeframes: list[str]) -> dict[str, float | None]:
    """Predict slopes for multiple timeframes. Returns {timeframe: slope}."""
    results = {}
    for tf in timeframes:
        results[tf] = predict_slope(symbol, tf)
    return results


def fine_tune(symbol: str, timeframe: str, epochs: int = 5, batch_size: int = 64) -> bool:
    """Fine-tune an existing model with the latest klines data.

    Fetches recent klines, builds features and targets, and trains
    for a few epochs. Saves the updated model back to disk.

    Returns True on success, False on failure.
    """
    import tensorflow as tf

    model, meta = _load_model(symbol, timeframe)
    if model is None:
        logger.error(f"No model found for {symbol}/{timeframe}")
        return False

    params = meta["params"]
    window = params["WINDOW"]
    smooth_win = params.get("SMOOTH_WIN", 8)

    # Fetch a good amount of recent data for fine-tuning
    limit = window * 10
    klines = fetch_klines(symbol, interval=timeframe, limit=limit)
    if len(klines) < window + 10:
        logger.warning(f"Not enough klines for fine-tuning {symbol}/{timeframe}")
        return False

    closes = np.array([k["close"] for k in klines], dtype=np.float32)
    Z = _build_features(closes, meta)
    slope = _build_slope_target(closes, smooth_win)

    # Build windowed dataset
    xs, ys = [], []
    for i in range(len(Z) - window):
        label_idx = i + window
        if label_idx >= len(slope):
            break
        xs.append(Z[i:i + window])
        ys.append(slope[label_idx])

    if len(xs) < 10:
        logger.warning(f"Too few training windows for {symbol}/{timeframe}")
        return False

    X = np.array(xs, dtype=np.float32)
    y = np.array(ys, dtype=np.float32)

    # Fine-tune with a low learning rate
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4, clipnorm=1.0),
        loss="mse",
        metrics=["mae"],
    )
    model.fit(X, y, epochs=epochs, batch_size=batch_size, verbose=0)

    # Save updated model
    model_dir = _model_dir(symbol, timeframe)
    model.save(os.path.join(model_dir, "saved_model.keras"))
    model.save_weights(os.path.join(model_dir, "saved.weights.h5"))
    logger.info(f"Fine-tuned model for {symbol}/{timeframe} ({len(X)} windows, {epochs} epochs)")
    return True


def save_uploaded_model(symbol: str, timeframe: str, model_data: bytes) -> bool:
    """Save an uploaded model ZIP file to the models directory.

    The ZIP should contain: saved_model.keras, saved.weights.h5, meta.json
    """
    import io
    import zipfile

    model_dir = _model_dir(symbol, timeframe)
    os.makedirs(model_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(model_data)) as zf:
            names = zf.namelist()
            if "meta.json" not in names:
                logger.error("Uploaded model ZIP missing meta.json")
                return False
            zf.extractall(model_dir)
        logger.info(f"Saved uploaded model for {symbol}/{timeframe} to {model_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract model ZIP: {e}")
        return False
