
from pathlib import Path
import pandas as pd

csv_path = (
    Path(__file__).resolve().parents[1]
    / "datasets"
    / "telemetry"
    / "ai4i2020.csv"
)

df = pd.read_csv(csv_path)

print("Total records:", len(df))
print("Columns:", df.columns.tolist())
print("Missing values:", int(df.isna().sum().sum()))

print("\nMachine failures:")
print(df["Machine failure"].value_counts())

print("\nFailure categories:")
for col in ["TWF", "HDF", "PWF", "OSF", "RNF"]:
    print(col, int(df[col].sum()))
