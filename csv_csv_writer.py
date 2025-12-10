#!/usr/bin/env python3
"""
Utility to append a single row to a CSV file, creating header if needed.
"""
import csv
from pathlib import Path


def append_row_to_csv(csv_path: Path, row: dict) -> None:
    """Append a single row to a CSV file. If file does not exist, create with header from row keys."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    if not file_exists:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)
        return

    # If file exists, append
    with open(csv_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        # Ensure the header matches; if not, simply write without header
        # We assume existing header matches keys in row for MVP
        writer.writerow(row)



