from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "telemetry"
    / "ai4i2020.csv"
)

FAILURE_CATEGORY_COLUMNS = ["TWF", "HDF", "PWF", "OSF", "RNF"]

FAILURE_CATEGORY_LABELS = {
    "TWF": "Tool Wear Failure",
    "HDF": "Heat Dissipation Failure",
    "PWF": "Power Failure",
    "OSF": "Overstrain Failure",
    "RNF": "Random Failure",
}

DATASET_NAME = "AI4I 2020 Predictive Maintenance Dataset"
DATASET_SOURCE = "AI4I 2020 - Synthetic Dataset"

app = FastAPI(title="FactoryMind AI API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_dataset() -> pd.DataFrame:
    if not DATASET_PATH.exists():
        raise RuntimeError(f"AI4I dataset not found at {DATASET_PATH}")
    return pd.read_csv(DATASET_PATH)


DATASET = load_dataset()


def to_record(row: pd.Series) -> dict:
    air_k = float(row["Air temperature [K]"])
    process_k = float(row["Process temperature [K]"])
    flags = {name: int(row[name]) for name in FAILURE_CATEGORY_COLUMNS}
    active = [name for name in FAILURE_CATEGORY_COLUMNS if flags[name] == 1]

    return {
        "record_id": int(row["UDI"]),
        "product_id": str(row["Product ID"]),
        "machine_type": str(row["Type"]),
        "air_temperature_k": round(air_k, 2),
        "air_temperature_c": round(air_k - 273.15, 2),
        "process_temperature_k": round(process_k, 2),
        "process_temperature_c": round(process_k - 273.15, 2),
        "rotational_speed_rpm": int(row["Rotational speed [rpm]"]),
        "torque_nm": float(row["Torque [Nm]"]),
        "tool_wear_min": int(row["Tool wear [min]"]),
        "machine_failure": bool(int(row["Machine failure"])),
        "failure_flags": flags,
        "failure_types": active,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "project": "FactoryMind AI",
        "version": "0.2.0",
        "dataset": DATASET_NAME,
        "records": int(len(DATASET)),
    }


@app.get("/api/dataset/summary")
def dataset_summary():
    total = int(len(DATASET))
    failures = int((DATASET["Machine failure"] == 1).sum())
    normal = total - failures

    failure_categories = [
        {
            "code": code,
            "label": FAILURE_CATEGORY_LABELS[code],
            "count": int(DATASET[code].sum()),
        }
        for code in FAILURE_CATEGORY_COLUMNS
    ]

    machine_types = [
        {"type": machine_type, "count": int(count)}
        for machine_type, count in DATASET["Type"].value_counts().items()
    ]

    return {
        "dataset": DATASET_NAME,
        "source": DATASET_SOURCE,
        "record_count": total,
        "normal_count": normal,
        "failure_count": failures,
        "failure_rate": round(failures / total, 4) if total else 0.0,
        "failure_categories": failure_categories,
        "machine_types": machine_types,
    }


@app.get("/api/telemetry")
def telemetry(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    failure_only: bool = Query(False),
    normal_only: bool = Query(False),
    record_id: Optional[int] = Query(None, ge=1),
    machine_type: Optional[str] = Query(None),
):
    frame = DATASET

    if record_id is not None:
        frame = frame[frame["UDI"] == record_id]

    if failure_only:
        frame = frame[frame["Machine failure"] == 1]
    elif normal_only:
        frame = frame[frame["Machine failure"] == 0]

    if machine_type:
        frame = frame[frame["Type"] == machine_type.upper()]

    total = int(len(frame))
    window = frame.iloc[offset : offset + limit]
    records = [to_record(row) for _, row in window.iterrows()]

    return {
        "dataset": DATASET_NAME,
        "source": DATASET_SOURCE,
        "total": total,
        "limit": limit,
        "offset": offset,
        "returned": len(records),
        "records": records,
    }


@app.get("/api/telemetry/{record_id}")
def telemetry_record(record_id: int):
    match = DATASET[DATASET["UDI"] == record_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Record not found")
    return to_record(match.iloc[0])
