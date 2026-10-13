"""
AuthentiScore — Export Feedback Dataset Script
==============================================

Exports user feedback collected via POST /scan/{scan_id}/feedback
into an evaluation CSV dataset for continuous model retraining and drift analysis.
"""

import sys
import os
import argparse
import csv
from pathlib import Path

# Setup path to load backend app modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.mongodb import db


def export_feedback(output_path: Path):
    print(f"Connecting to MongoDB scan_feedback collection...")
    try:
        feedback_docs = list(db.scan_feedback.find({}))
    except Exception as exc:
        print(f"Warning: Failed to connect to MongoDB ({exc}). Falling back to empty export.")
        feedback_docs = []

    print(f"Found {len(feedback_docs)} feedback entries.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "feedback_id",
        "scan_id",
        "user_id",
        "username",
        "platform",
        "user_verdict",
        "system_score",
        "system_classification",
        "rating",
        "comment",
        "timestamp",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for doc in feedback_docs:
            writer.writerow(doc)

    print(f"Exported {len(feedback_docs)} records to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export AuthentiScore feedback dataset")
    parser.add_argument(
        "--output",
        type=str,
        default=str(backend_dir / "eval" / "feedback_dataset.csv"),
        help="Path to output CSV file"
    )
    args = parser.parse_args()
    export_feedback(Path(args.output))


if __name__ == "__main__":
    main()
