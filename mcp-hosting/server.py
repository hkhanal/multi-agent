from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
import joblib
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("df-and-models")

DATA_PATH = os.getenv("DATA_PATH", "/data/data.csv")
MODELS_DIR = os.getenv("MODELS_DIR", "/models")
FEATURE_CONFIG_PATH = os.getenv("FEATURE_CONFIG_PATH", f"{MODELS_DIR}/feature_config.json")
MAX_RETURN_ROWS = int(os.getenv("MAX_RETURN_ROWS", "200"))

# -------- data --------
def load_df(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"DATA_PATH not found: {path}")
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    if path.lower().endswith(".parquet"):
        return pd.read_parquet(path)
    raise ValueError("Unsupported data type. Use .csv or .parquet")

DF = load_df(DATA_PATH)

# -------- models --------
def load_feature_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"feature_config.json not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

FEATURE_CFG = load_feature_config(FEATURE_CONFIG_PATH)

# lazy-loaded model cache
_MODEL_CACHE: Dict[str, Any] = {}

def _get_model(model_name: str):
    if model_name not in FEATURE_CFG:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(FEATURE_CFG.keys())}")
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    # expected filenames: classifier1.joblib, classifier2.joblib
    model_path = os.path.join(MODELS_DIR, f"{model_name}.joblib")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model = joblib.load(model_path)
    _MODEL_CACHE[model_name] = model
    return model

def _row_by_id(df: pd.DataFrame, id_col: str, id_value: Union[str, int]) -> pd.Series:
    if id_col not in df.columns:
        raise ValueError(f"id_column '{id_col}' not in dataframe columns")

    # try both string/int matching safely
    matches = df[df[id_col].astype(str) == str(id_value)]
    if matches.empty:
        raise ValueError(f"No row found for {id_col}={id_value}")
    # If duplicates exist, pick the first (or change to raise)
    return matches.iloc[0]

def _build_features(row: pd.Series, feature_cols: List[str], overrides: Optional[Dict[str, Any]]) -> pd.DataFrame:
    data = row.to_dict()
    if overrides:
        # allow user-provided values to override row values (e.g., date, name, etc.)
        data.update(overrides)

    missing = [c for c in feature_cols if c not in data]
    if missing:
        raise ValueError(f"Missing required features after overrides: {missing}")

    # one-row dataframe for sklearn
    X = pd.DataFrame([{c: data[c] for c in feature_cols}])
    return X

def _predict(model: Any, X: pd.DataFrame, labels: Optional[List[str]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    # classification label
    if hasattr(model, "predict"):
        pred = model.predict(X)
        out["prediction"] = pred[0] if hasattr(pred, "__len__") else pred

    # probabilities if available
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[0]
        if labels and len(labels) == len(proba):
            out["probabilities"] = {labels[i]: float(proba[i]) for i in range(len(proba))}
        else:
            out["probabilities"] = [float(p) for p in proba]

    return out

# -------- tools --------
@mcp.tool()
def list_models() -> Dict[str, Any]:
    """List available models and their required features."""
    return {
        "models": {
            name: {
                "id_column": cfg.get("id_column", "id"),
                "feature_columns": cfg.get("feature_columns", []),
                "target_labels": cfg.get("target_labels", None),
            }
            for name, cfg in FEATURE_CFG.items()
        }
    }

@mcp.tool()
def get_schema() -> Dict[str, Any]:
    """Return dataframe columns and dtypes."""
    return {
        "data_path": DATA_PATH,
        "columns": [{"name": c, "dtype": str(DF[c].dtype)} for c in DF.columns],
        "row_count": int(len(DF)),
    }

@mcp.tool()
def get_row(id_value: Union[str, int], id_column: str = "id") -> Dict[str, Any]:
    """Fetch a single row by id (useful for debugging)."""
    row = _row_by_id(DF, id_column, id_value)
    return {"id_column": id_column, "id_value": id_value, "row": row.to_dict()}

@mcp.tool()
def predict_from_id(
    model_name: Literal["classifier1", "classifier2"],
    id_value: Union[str, int],
    overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main tool: user provides id + optional info (name/date/etc). Server:
    - finds row by id
    - builds features for the chosen model (with overrides)
    - runs inference
    """
    cfg = FEATURE_CFG[model_name]
    id_col = cfg.get("id_column", "id")
    feature_cols = cfg.get("feature_columns", [])
    labels = cfg.get("target_labels")

    row = _row_by_id(DF, id_col, id_value)
    X = _build_features(row, feature_cols, overrides)

    model = _get_model(model_name)
    pred_out = _predict(model, X, labels)

    return {
        "model": model_name,
        "id_column": id_col,
        "id_value": id_value,
        "features_used": feature_cols,
        "overrides_used": list(overrides.keys()) if overrides else [],
        **pred_out
    }

app = mcp.streamable_http_app()
