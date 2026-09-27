import io
import json
from pathlib import Path

import pandas as pd


MAX_ROWS = 100_000
ALLOWED_OPERATIONS = {
    "summary", "missing_values", "group_mean", "filter", "sort", "create_column"
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
                "numeric": json.loads(frame.describe(include="number").to_json())}
    if operation == "missing_values":
        return frame.isna().sum().astype(int).to_dict()
    if operation == "group_mean":
        group_by = parameters.get("by")
        column = parameters.get("column")
        _require_columns(frame, group_by, column)
        return frame.groupby(group_by, dropna=False)[column].mean().reset_index().to_dict("records")
    if operation == "filter":
        column = parameters.get("column")
        _require_columns(frame, column)
        return frame[frame[column].astype(str) == str(parameters.get("value"))].head(1000).to_dict("records")
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


def _require_columns(frame, *columns):
    missing = [column for column in columns if not isinstance(column, str) or column not in frame.columns]
    if missing:
        raise ValueError(f"Unknown column: {missing[0]}")


def modified_filename(filename):
    path = Path(filename)
    return f"{path.stem}_modified{path.suffix or '.csv'}"