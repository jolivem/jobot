"""LSTM slope model training.

Adapted from cryptool/ai/lstm/train_crypto_slope_grid_search.py.
Uses jobot's klines_fetcher to download data from Binance instead of
the cryptool utils/fetchonbinance pipeline.

Usage (from the jobot project root):
    python -m app.services.lstm_training --symbol ETHUSDC --timeframe 15m --days 180

This produces a model directory under LSTM_MODELS_DIR/{symbol}/{timeframe}/
containing saved_model.keras, saved.weights.h5, and meta.json.
"""

import argparse
import json
import logging
import os
import traceback
from datetime import datetime

import numpy as np
import pandas as pd
import tensorflow as tf

from app.core.config import settings
from app.services.klines_fetcher import fetch_klines

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ===================== Default hyperparameters =====================
DEFAULTS = {
    "SMOOTH_WIN": 8,
    "WINDOW": 64,
    "USE_EMA_FAST": True,
    "USE_LOGRET": True,
    "USE_VOL24": False,
    "LSTM_UNITS": 64,
    "LEARNING_RATE": 1e-3,
}

SEED = 42
TRAIN_SPLIT = 0.70
VAL_SPLIT = 0.15
SLOPE_HORIZON = 1
EPOCHS = 60
BATCH_SIZE = 128
ES_PATIENCE = 6
WEIGHT_START = 0.7
WEIGHT_END = 1.3
VAL_FOCUS_MAXK = 256
CLIPNORM = 1.0


# ===================== GPU setup =====================
def _setup_gpu():
    gpus = tf.config.list_physical_devices("GPU")
    for g in gpus:
        try:
            tf.config.experimental.set_memory_growth(g, True)
        except Exception:
            pass
    if gpus:
        logger.info(f"GPU(s) detected: {[g.name for g in gpus]}")
    else:
        logger.info("No GPU detected, using CPU")


# ===================== Data pipeline =====================
def _check_and_fix_feature(x):
    s = pd.Series(x)
    s = s.replace([np.inf, -np.inf], np.nan)
    s = s.interpolate().bfill().ffill()
    return s.values.astype(np.float32)


def _fetch_close_prices(symbol: str, interval: str, days: int) -> np.ndarray:
    """Fetch close prices from Binance using jobot's klines_fetcher."""
    # Estimate number of candles based on interval and days
    interval_minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "6h": 360,
        "8h": 480, "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080,
    }
    minutes_per_candle = interval_minutes.get(interval, 60)
    limit = (days * 24 * 60) // minutes_per_candle
    limit = min(limit, 50000)  # safety cap

    logger.info(f"Fetching {limit} klines for {symbol} ({interval}, ~{days} days)...")
    klines = fetch_klines(symbol, interval=interval, limit=limit)
    logger.info(f"Fetched {len(klines)} klines")

    if len(klines) < 200:
        raise RuntimeError(f"Not enough klines: {len(klines)} (need at least 200)")

    closes = np.array([k["close"] for k in klines], dtype=np.float32)
    return closes


def _build_dataset(closes: np.ndarray, params: dict, H: int = 1) -> dict:
    """Build features, targets, and train/val/test splits from close prices."""
    T = len(closes)
    n_train = int(T * TRAIN_SPLIT)
    n_val = int(T * VAL_SPLIT)
    train_slice = slice(0, n_train)
    val_slice = slice(n_train, n_train + n_val)
    test_slice = slice(n_train + n_val, T)

    # Raw slope (k=1)
    slope_raw = np.empty_like(closes)
    slope_raw[:] = np.nan
    slope_raw[SLOPE_HORIZON:] = closes[SLOPE_HORIZON:] - closes[:-SLOPE_HORIZON]
    slope_raw[:SLOPE_HORIZON] = slope_raw[SLOPE_HORIZON]
    slope_raw = _check_and_fix_feature(slope_raw)

    # EMA smoothing
    slope_true = (
        pd.Series(slope_raw)
        .ewm(span=params["SMOOTH_WIN"], adjust=False)
        .mean()
        .bfill()
        .ffill()
        .values.astype(np.float32)
    )

    # Features
    feat_list = []
    feat_names = []

    # close
    feat_list.append(_check_and_fix_feature(closes))
    feat_names.append("close")

    # ema fast
    if params["USE_EMA_FAST"]:
        ema = pd.Series(closes).ewm(span=6, adjust=False).mean().values.astype(np.float32)
        feat_list.append(_check_and_fix_feature(ema))
        feat_names.append("ema6")

    # log returns
    if params["USE_LOGRET"]:
        logret = np.zeros_like(closes, dtype=np.float32)
        base = np.clip(closes[:-1], 1e-8, 1e12)
        logret[1:] = np.log(np.clip(closes[1:] / base, 1e-8, 1e8)).astype(np.float32)
        feat_list.append(_check_and_fix_feature(logret))
        feat_names.append("logret")

    # vol24
    if params["USE_VOL24"]:
        lr_idx = feat_names.index("logret") if "logret" in feat_names else -1
        if lr_idx >= 0:
            lr = feat_list[lr_idx]
        else:
            lr = np.zeros_like(closes, dtype=np.float32)
        vol = pd.Series(lr).rolling(window=24, min_periods=1).std().values.astype(np.float32)
        feat_list.append(_check_and_fix_feature(vol))
        feat_names.append("vol24")

    Z = np.stack(feat_list, axis=-1).astype(np.float32)
    n_features = Z.shape[-1]

    # z-score (train stats only)
    def zscore_train(x, slc):
        mu = np.nanmean(x[slc])
        sd = np.nanstd(x[slc])
        if not np.isfinite(sd) or sd < 1e-12:
            sd = 1.0
        z = (x - mu) / sd
        z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
        return z.astype(np.float32), float(mu), float(sd)

    Zz = np.empty_like(Z)
    mus, sds = [], []
    for j in range(n_features):
        Zz[:, j], mu_j, sd_j = zscore_train(Z[:, j], train_slice)
        mus.append(mu_j)
        sds.append(sd_j)

    # Target (real units)
    y_mu = float(np.nanmean(slope_true[train_slice]))
    y_sd = float(np.nanstd(slope_true[train_slice]))
    z_slope = slope_true.astype(np.float32)

    # Build windows
    def make_windows(Zz, y, slc, window, horizon):
        """Build sliding windows. Window can reach back before slc.start
        (into prior data) as long as the label stays within the slice."""
        xs, ys = [], []
        start, end = slc.start, slc.stop
        for label_idx in range(start + horizon, end):
            win_start = label_idx - horizon - window + 1
            if win_start < 0:
                continue
            xs.append(Zz[win_start : win_start + window, :])
            ys.append(y[label_idx])
        if not xs:
            return np.empty((0, window, Zz.shape[-1]), dtype=np.float32), np.empty((0,), dtype=np.float32)
        return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)

    def drop_bad(X, y):
        if len(X) == 0:
            return X, y
        mask = np.isfinite(X).all(axis=(1, 2)) & np.isfinite(y)
        return X[mask], y[mask]

    window = params["WINDOW"]

    # Auto-reduce window if not enough data
    min_windows_needed = 10
    max_window = (T - min_windows_needed * 3) // 2  # rough upper bound
    if window > max_window and max_window >= 8:
        logger.warning(f"WINDOW={window} too large for {T} candles, reducing to {max_window}")
        window = max_window
        params = dict(params)
        params["WINDOW"] = window

    Xtr, ytr = make_windows(Zz, z_slope, train_slice, window, H)
    Xva, yva = make_windows(Zz, z_slope, val_slice, window, H)
    Xte, yte = make_windows(Zz, z_slope, test_slice, window, H)

    Xtr, ytr = drop_bad(Xtr, ytr)
    Xva, yva = drop_bad(Xva, yva)
    Xte, yte = drop_bad(Xte, yte)

    if len(Xtr) == 0 or len(Xva) == 0 or len(Xte) == 0:
        raise RuntimeError(
            f"Not enough valid windows (train={len(Xtr)}, val={len(Xva)}, test={len(Xte)}) "
            f"with WINDOW={window} and {T} candles. Get more data or reduce WINDOW."
        )

    return {
        "Xtr": Xtr, "ytr": ytr,
        "Xva": Xva, "yva": yva,
        "Xte": Xte, "yte": yte,
        "n_features": n_features,
        "y_mu": y_mu, "y_sd": y_sd,
        "feat_mus": mus, "feat_sds": sds,
        "feat_names": feat_names,
    }


# ===================== Model =====================
def _build_model(n_features: int, params: dict):
    inputs = tf.keras.Input(shape=(params["WINDOW"], n_features))
    x = tf.keras.layers.LSTM(params["LSTM_UNITS"], return_sequences=False)(inputs)
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(1)(x)
    model = tf.keras.Model(inputs, outputs)
    opt = tf.keras.optimizers.Adam(learning_rate=params["LEARNING_RATE"], clipnorm=CLIPNORM)
    model.compile(optimizer=opt, loss="mse", metrics=["mae"])
    return model


def _save_model(save_dir: str, model, data: dict, params: dict, H: int, history=None):
    os.makedirs(save_dir, exist_ok=True)

    model.save(os.path.join(save_dir, "saved_model.keras"))
    model.save_weights(os.path.join(save_dir, "saved.weights.h5"))

    meta = {
        "H": int(H),
        "params": params,
        "n_features": int(data["n_features"]),
        "y_mu": data["y_mu"],
        "y_sd": data["y_sd"],
        "feat_mus": data["feat_mus"],
        "feat_sds": data["feat_sds"],
        "feat_names": data["feat_names"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    with open(os.path.join(save_dir, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if history is not None:
        hist = {k: [float(v) for v in vs] for k, vs in history.history.items()}
        with open(os.path.join(save_dir, "history.json"), "w") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)


# ===================== Training =====================
def train(symbol: str, timeframe: str, days: int = 180, params: dict | None = None) -> dict:
    """Train an LSTM slope model for a symbol/timeframe.

    Args:
        symbol: Trading pair (e.g., "ETHUSDC").
        timeframe: Candle interval (e.g., "15m", "1d", "1w").
        days: Number of days of historical data to use.
        params: Hyperparameters (defaults to DEFAULTS if None).

    Returns:
        Dict with training results (metrics, model path).
    """
    _setup_gpu()
    tf.keras.utils.set_random_seed(SEED)
    np.random.seed(SEED)

    if params is None:
        params = dict(DEFAULTS)

    logger.info(f"Training LSTM model for {symbol}/{timeframe} ({days} days)")
    logger.info(f"Params: {json.dumps(params)}")

    result = {"symbol": symbol, "timeframe": timeframe, "params": params}

    try:
        # Fetch data
        closes = _fetch_close_prices(symbol, timeframe, days)
        logger.info(f"Data: {len(closes)} candles")

        # Build dataset
        data = _build_dataset(closes, params, H=1)
        logger.info(
            f"Windows: train={len(data['Xtr'])}, val={len(data['Xva'])}, test={len(data['Xte'])}"
        )

        # Sample weighting (recent data weighted higher)
        sample_weight = np.linspace(WEIGHT_START, WEIGHT_END, len(data["ytr"])).astype(np.float32)

        # Focused validation (last N windows)
        K = min(VAL_FOCUS_MAXK, len(data["Xva"]))
        Xva_focus = data["Xva"][-K:]
        yva_focus = data["yva"][-K:]

        # Build and train
        model = _build_model(data["n_features"], params)
        cb = tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=ES_PATIENCE, restore_best_weights=True
        )
        history = model.fit(
            data["Xtr"], data["ytr"],
            validation_data=(Xva_focus, yva_focus),
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            callbacks=[cb],
            sample_weight=sample_weight,
            verbose=1,
        )

        # Evaluate
        test_mse, test_mae = model.evaluate(data["Xte"], data["yte"], verbose=0)
        test_rmse = float(np.sqrt(test_mse))
        yhat = model.predict(data["Xte"], verbose=0).ravel().astype(np.float32)
        ytrue = data["yte"].astype(np.float32)

        corr = float("nan")
        dir_acc = float("nan")
        if np.isfinite(yhat).all() and np.isfinite(ytrue).all() and len(ytrue) > 1:
            corr = float(np.corrcoef(ytrue, yhat)[0, 1])
            dir_acc = float(np.mean(np.sign(ytrue) == np.sign(yhat)))

        # Save model
        save_dir = os.path.join(settings.LSTM_MODELS_DIR, symbol.upper(), timeframe)
        _save_model(save_dir, model, data, params, H=1, history=history)

        result.update({
            "status": "ok",
            "model_dir": save_dir,
            "candles": len(closes),
            "train_windows": len(data["Xtr"]),
            "test_mse": float(test_mse),
            "test_rmse": test_rmse,
            "test_mae": float(test_mae),
            "test_corr": corr,
            "test_dir_acc": dir_acc,
            "epochs_run": len(history.history["loss"]),
        })

        logger.info(
            f"Training complete: MAE={test_mae:.6f}, RMSE={test_rmse:.6f}, "
            f"corr={corr:.3f}, dir_acc={dir_acc:.3f}"
        )

    except Exception as e:
        result.update({"status": "fail", "error": str(e), "trace": traceback.format_exc()})
        logger.error(f"Training failed: {e}", exc_info=True)

    return result


def train_all_timeframes(symbol: str, timeframes: str, days: int = 180) -> list[dict]:
    """Train models for all timeframes of a symbol.

    Args:
        symbol: Trading pair (e.g., "ETHUSDC").
        timeframes: Comma-separated timeframes (e.g., "15m,1d,1w").
        days: Number of days of data.

    Returns:
        List of training result dicts.
    """
    results = []
    for tf in timeframes.split(","):
        tf = tf.strip()
        logger.info(f"\n{'='*60}\nTraining {symbol}/{tf}\n{'='*60}")
        result = train(symbol, tf, days=days)
        results.append(result)
    return results


# ===================== CLI =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LSTM slope model")
    parser.add_argument("--symbol", required=True, help="Trading pair (e.g., ETHUSDC)")
    parser.add_argument(
        "--timeframe",
        default=None,
        help="Single timeframe (e.g., 15m). Use --timeframes for multiple.",
    )
    parser.add_argument(
        "--timeframes",
        default=None,
        help="Comma-separated timeframes (e.g., 15m,1d,1w)",
    )
    parser.add_argument("--days", type=int, default=180, help="Days of history (default: 180)")

    args = parser.parse_args()

    if args.timeframes:
        results = train_all_timeframes(args.symbol, args.timeframes, days=args.days)
    elif args.timeframe:
        results = [train(args.symbol, args.timeframe, days=args.days)]
    else:
        parser.error("Specify --timeframe or --timeframes")

    # Summary
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    for r in results:
        status = r.get("status", "?")
        if status == "ok":
            print(
                f"  {r['symbol']}/{r['timeframe']}: OK "
                f"(MAE={r['test_mae']:.6f}, dir_acc={r['test_dir_acc']:.3f}, "
                f"{r['epochs_run']} epochs)"
            )
        else:
            print(f"  {r['symbol']}/{r['timeframe']}: FAIL - {r.get('error')}")
