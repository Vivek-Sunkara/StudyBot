import io
import json
from pathlib import Path

import pandas as pd


MAX_ROWS = 100_000
ALLOWED_OPERATIONS = {
    "summary", "columns", "describe", "head", "tail", "dtypes",
    "unique_values", "value_counts", "missing_values", "group_mean",
    "group_agg", "filter", "sort", "create_column", "mean", "median",
    "sum", "min", "max", "count", "std", "corr", "quantile"
}


def _load_csv(data):
    frame = pd.read_csv(io.BytesIO(data), nrows=MAX_ROWS + 1)
    if len(frame) > MAX_ROWS:
        raise ValueError(f"CSV exceeds the {MAX_ROWS} row limit")
    return frame


def analyze_csv(data, operation, parameters=None):
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError("Unsupported data operation")
    frame = _load_csv(data)
    parameters = parameters or {}

    if operation == "summary":
        return {"rows": len(frame), "columns": list(frame.columns),
                "dtypes": {k: str(v) for k, v in frame.dtypes.items()},
                "missing_values": frame.isna().sum().astype(int).to_dict(),
                "describe": json.loads(frame.describe(include="all").fillna("").to_json())}
    if operation == "columns":
        return list(frame.columns)
    if operation == "describe":
        return json.loads(frame.describe(include="all").fillna("").to_json())
    if operation == "head":
        return frame.head(_limit(parameters.get("rows"))).to_dict("records")
    if operation == "tail":
        return frame.tail(_limit(parameters.get("rows"))).to_dict("records")
    if operation == "dtypes":
        return {column: str(dtype) for column, dtype in frame.dtypes.items()}
    if operation == "unique_values":
        column = parameters.get("column")
        _require_columns(frame, column)
        return frame[column].dropna().unique().tolist()[:1000]
    if operation == "value_counts":
        column = parameters.get("column")
        _require_columns(frame, column)
        return frame[column].value_counts(dropna=False).head(1000).to_dict()
    if operation == "missing_values":
        return frame.isna().sum().astype(int).to_dict()
    if operation == "group_mean":
        group_by = parameters.get("by")
        column = parameters.get("column")
        _require_columns(frame, group_by, column)
        return frame.groupby(group_by, dropna=False)[column].mean().reset_index().to_dict("records")
    if operation == "group_agg":
        group_by = parameters.get("by")
        column = parameters.get("column")
        agg = parameters.get("agg", "mean")
        _require_columns(frame, group_by, column)
        if agg not in {"mean", "sum", "median", "min", "max", "count", "std"}:
            raise ValueError("Unsupported aggregation")
        result = getattr(frame.groupby(group_by, dropna=False)[column], agg)()
        return result.reset_index().to_dict("records")
    if operation == "filter":
        column = parameters.get("column")
        _require_columns(frame, column)
        value = parameters.get("value")
        if value is None:
            raise ValueError("filter requires a value")
        return frame[frame[column].astype(str) == str(value)].head(1000).to_dict("records")
    if operation == "sort":
        column = parameters.get("column")
        _require_columns(frame, column)
        return frame.sort_values(column, ascending=bool(parameters.get("ascending", True))).head(1000).to_dict("records")
    if operation == "create_column":
        name = parameters.get("name")
        source = parameters.get("source")
        multiplier = parameters.get("multiplier", 1)
        _require_columns(frame, source)
        if not isinstance(name, str) or not name.strip() or not isinstance(multiplier, (int, float)):
            raise ValueError("create_column requires a name and numeric multiplier")
        frame[name] = frame[source] * multiplier
        return frame.to_csv(index=False).encode("utf-8")

    if operation in {"mean", "median", "sum", "min", "max", "count", "std"}:
        column = parameters.get("column")
        _require_columns(frame, column)
        series = pd.to_numeric(frame[column], errors="coerce")
        if operation == "mean":
            return float(series.mean()) if not series.empty else None
        if operation == "median":
            return float(series.median()) if not series.empty else None
        if operation == "sum":
            return float(series.sum()) if not series.empty else 0.0
        if operation == "min":
            return float(series.min()) if not series.empty else None
        if operation == "max":
            return float(series.max()) if not series.empty else None
        if operation == "count":
            return int(series.count())
        if operation == "std":
            return float(series.std()) if series.count() > 1 else 0.0

    if operation == "corr":
        left = parameters.get("left")
        right = parameters.get("right")
        _require_columns(frame, left, right)
        left_series = pd.to_numeric(frame[left], errors="coerce")
        right_series = pd.to_numeric(frame[right], errors="coerce")
        pair = pd.concat([left_series, right_series], axis=1).dropna()
        if pair.empty:
            return None
        return float(pair[left].corr(pair[right]))

    if operation == "quantile":
        column = parameters.get("column")
        q = parameters.get("q", 0.5)
        _require_columns(frame, column)
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            return None
        return float(series.quantile(q))

    raise ValueError(f"Unsupported data operation: {operation}")


def _require_columns(frame, *columns):
    missing = [column for column in columns if not isinstance(column, str) or column not in frame.columns]
    if missing:
        raise ValueError(f"Unknown column: {missing[0]}")


def _limit(value):
    if value is None:
        return 5
    if not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("rows must be an integer from 1 to 100")
    return value


def modified_filename(filename):
    path = Path(filename)
    return f"{path.stem}_modified{path.suffix or '.csv'}"