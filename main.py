"""
main.py - Run the complete project pipeline with ONE command
============================================================

    python main.py

Steps:
    1. Generate the raw dataset            (src/generate_dataset.py)
    2. Clean the data + feature engineering (src/data_cleaning.py)
    3. Run the analysis and print a summary (src/analysis.py)
    4. Load into SQLite and run SQL queries (src/sql_analysis.py)
    5. Create the report charts             (src/visualizations.py)
    6. Build the Excel + Markdown reports   (src/report_generator.py)

Afterwards, open the interactive dashboard with:
    streamlit run dashboard/app.py
"""

import sys
import time
from pathlib import Path

# Make the "src" folder importable
sys.path.append(str(Path(__file__).resolve().parent / "src"))

import analysis  # noqa: E402
import data_cleaning  # noqa: E402
import generate_dataset  # noqa: E402
import report_generator  # noqa: E402
import sql_analysis  # noqa: E402
import visualizations  # noqa: E402

STEPS = [
    ("Generate dataset", generate_dataset.main),
    ("Clean data", data_cleaning.main),
    ("Analyse data", analysis.main),
    ("SQL analysis", sql_analysis.main),
    ("Create charts", visualizations.main),
    ("Build reports", report_generator.main),
]


def main():
    start = time.time()
    for number, (name, step) in enumerate(STEPS, start=1):
        print(f"\n{'#' * 70}\n# STEP {number}/{len(STEPS)}: {name}\n{'#' * 70}")
        step()
    print(f"\nPipeline finished in {time.time() - start:.1f} seconds.")
    print("Open the dashboard with:  streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
