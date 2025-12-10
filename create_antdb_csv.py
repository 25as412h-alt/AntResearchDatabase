#!/usr/bin/env python3
"""
CSV -> AntDB importer
- species.csv -> 種マスター
- research.csv -> 文献情報
- records.csv -> 観測記録
"""

import argparse
from pathlib import Path

try:
    from csv_importer import AntDatabaseImporter
except Exception:
    AntDatabaseImporter = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import CSV data into AntDB using the existing importer.")
    parser.add_argument("--db", default="ant_research.db", help="Database file path")
    parser.add_argument("--data", default="csv_data", help="Directory containing species.csv, research.csv, records.csv")
    args = parser.parse_args()

    if AntDatabaseImporter is None:
        print("Error: csv_importer module not found. Ensure this script is run from project root.")
        return 2

    importer = AntDatabaseImporter(str(args.db))
    try:
        data_dir = Path(args.data)
        # If the provided data directory doesn't exist, try a common fallback directory named 'csv'
        if not data_dir.exists() or not data_dir.is_dir():
            alt_dir = Path("csv")
            if alt_dir.exists() and alt_dir.is_dir():
                print(f"Directory '{data_dir}' not found. Falling back to '{alt_dir}'.")
                data_dir = alt_dir
            else:
                print(f"Error: Data directory '{data_dir}' not found and no fallback 'csv' exists.")
                return 1

        if (data_dir / "species.csv").exists():
            importer.import_species(data_dir / "species.csv")
        else:
            print(f"Warning: {data_dir / 'species.csv'} not found")

        if (data_dir / "research.csv").exists():
            importer.import_research(data_dir / "research.csv")
        else:
            print(f"Warning: {data_dir / 'research.csv'} not found")

        if (data_dir / "records.csv").exists():
            importer.import_records(data_dir / "records.csv")
        else:
            print(f"Warning: {data_dir / 'records.csv'} not found")

        try:
            importer.conn.commit()
        except Exception:
            pass

        importer.save_error_log()
        print("✅ Import completed.")
        return 0
    except Exception as exc:
        print(f"Import error: {exc}")
        return 1
    finally:
        importer.close()


if __name__ == "__main__":
    raise SystemExit(main())


