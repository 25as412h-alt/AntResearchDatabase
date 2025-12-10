#!/usr/bin/env python3
"""
アリ類研究データベース CSVインポーター (MVP版)
使用法: python csv_importer.py --db ant_research.db --data ./csv_data/
"""

import sqlite3
import pandas as pd
import unicodedata
import hashlib
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class AntDatabaseImporter:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = sqlite3.Row
        self.error_log = []
    
    def normalize(self, text: str) -> str:
        """文字列正規化 (NFKC + strip)"""
        if pd.isna(text):
            return ""
        return unicodedata.normalize('NFKC', str(text).strip())
    
    def get_or_create_id(self, table: str, name_col: str, name: str) -> Optional[int]:
        """マスターテーブルからID取得、なければ作成"""
        normalized = self.normalize(name)
        if not normalized:
            return None
        
        cursor = self.conn.execute(
            f"SELECT id FROM {table} WHERE {name_col} = ? COLLATE NOCASE",
            (normalized,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # 新規作成
        cursor = self.conn.execute(
            f"INSERT INTO {table} ({name_col}) VALUES (?) RETURNING id",
            (normalized,)
        )
        return cursor.fetchone()[0]
    
    def resolve_species(self, name: str) -> Optional[int]:
        """種名を解決してspecies.idを返す"""
        normalized = self.normalize(name)
        if not normalized:
            return None
        
        # synonymsテーブルから検索
        cursor = self.conn.execute(
            "SELECT species_id FROM species_synonyms WHERE name_normalized = ?",
            (normalized,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # 直接speciesテーブルから検索 (学名)
        cursor = self.conn.execute(
            "SELECT id FROM species WHERE scientific_name = ? COLLATE NOCASE",
            (normalized,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # 和名でも検索
        cursor = self.conn.execute(
            "SELECT id FROM species WHERE japanese_name = ? COLLATE NOCASE",
            (normalized,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
    def import_species(self, csv_path: str):
        """種マスターのインポート"""
        logger.info(f"Importing species from {csv_path}")
        df = pd.read_csv(csv_path)
        
        for idx, row in df.iterrows():
            try:
                sci_name = self.normalize(row['scientific_name'])
                jpn_name = self.normalize(row['japanese_name'])
                
                # 種を登録 (重複は無視)
                cursor = self.conn.execute("""
                    INSERT OR IGNORE INTO species 
                    (scientific_name, japanese_name, subfamily, body_len_mm, red_list)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sci_name,
                    jpn_name,
                    self.normalize(row.get('subfamily', '')),
                    row.get('body_len_mm') if pd.notna(row.get('body_len_mm')) else None,
                    self.normalize(row.get('red_list', ''))
                ))
                
                # species_idを取得
                species_id = self.resolve_species(sci_name)
                if not species_id:
                    continue
                
                # synonyms登録 (学名・和名)
                for name in [sci_name, jpn_name]:
                    self.conn.execute("""
                        INSERT OR IGNORE INTO species_synonyms 
                        (species_id, name, name_normalized, synonym_type)
                        VALUES (?, ?, ?, ?)
                    """, (species_id, name, name, 'primary'))
                
                # 追加synonyms (カンマ区切り)
                if pd.notna(row.get('synonyms')):
                    synonyms = row['synonyms'].split(',')
                    for syn in synonyms:
                        syn_norm = self.normalize(syn)
                        if syn_norm:
                            self.conn.execute("""
                                INSERT OR IGNORE INTO species_synonyms 
                                (species_id, name, name_normalized, synonym_type)
                                VALUES (?, ?, ?, 'alias')
                            """, (species_id, syn, syn_norm))
                
                self.conn.commit()
                logger.info(f"✓ {sci_name} ({jpn_name})")
                
            except Exception as e:
                self.error_log.append(f"Row {idx}: {e}")
                logger.error(f"Row {idx}: {e}")
    
    def import_research(self, csv_path: str):
        """文献情報のインポート"""
        logger.info(f"Importing research from {csv_path}")
        df = pd.read_csv(csv_path)
        
        for idx, row in df.iterrows():
            try:
                title = self.normalize(row['title'])
                author = self.normalize(row['author'])
                year = int(row['year'])
                
                self.conn.execute("""
                    INSERT OR IGNORE INTO research (title, author, year, doi, file_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    title,
                    author,
                    year,
                    self.normalize(row.get('doi', '')),
                    self.normalize(row.get('file_path', ''))
                ))
                self.conn.commit()
                logger.info(f"✓ {title} ({year})")
                
            except Exception as e:
                self.error_log.append(f"Row {idx}: {e}")
                logger.error(f"Row {idx}: {e}")
    
    def import_records(self, csv_path: str):
        """観測記録のインポート (最重要)"""
        logger.info(f"Importing records from {csv_path}")
        df = pd.read_csv(csv_path)
        
        for idx, row in df.iterrows():
            try:
                # 1. 文献を特定
                research_title = self.normalize(row['research_title'])
                cursor = self.conn.execute(
                    "SELECT id FROM research WHERE title = ? COLLATE NOCASE",
                    (research_title,)
                )
                research_row = cursor.fetchone()
                if not research_row:
                    raise ValueError(f"Research not found: {research_title}")
                research_id = research_row[0]
                
                # 2. 環境・手法のID取得
                env_id = self.get_or_create_id('environment_types', 'name', 
                                                row.get('environment', 'その他'))
                method_id = self.get_or_create_id('methods', 'name', 
                                                   row.get('method', 'その他'))
                
                # 3. 調査地点を取得または作成
                site_name = self.normalize(row['site_name'])
                survey_date = self.normalize(row.get('survey_date', ''))
                lat = float(row['latitude']) if pd.notna(row.get('latitude')) else None
                lon = float(row['longitude']) if pd.notna(row.get('longitude')) else None
                elev = int(row['elevation_m']) if pd.notna(row.get('elevation_m')) else None
                
                cursor = self.conn.execute("""
                    SELECT id FROM survey_sites
                    WHERE research_id = ? AND site_name = ? 
                    AND COALESCE(survey_date, '') = ?
                    AND COALESCE(latitude, 0) = COALESCE(?, 0)
                    AND COALESCE(longitude, 0) = COALESCE(?, 0)
                """, (research_id, site_name, survey_date or '', lat or 0, lon or 0))
                
                site_row = cursor.fetchone()
                if site_row:
                    site_id = site_row[0]
                else:
                    cursor = self.conn.execute("""
                        INSERT INTO survey_sites 
                        (research_id, site_name, survey_date, env_type_id, 
                         latitude, longitude, elevation_m)
                        VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
                    """, (research_id, site_name, survey_date, env_id, lat, lon, elev))
                    site_id = cursor.fetchone()[0]
                
                # 4. 種を解決
                species_name = self.normalize(row['species_name'])
                species_id = self.resolve_species(species_name)
                if not species_id:
                    raise ValueError(f"Species not found: {species_name}")
                
                # 5. 出現記録を登録または更新
                abundance = int(row.get('abundance', 1))
                unit = self.normalize(row.get('unit', 'worker'))
                
                cursor = self.conn.execute("""
                    SELECT id, abundance FROM occurrences
                    WHERE site_id = ? AND species_id = ? 
                    AND method_id = ? AND unit = ?
                """, (site_id, species_id, method_id, unit))
                
                existing = cursor.fetchone()
                if existing:
                    # 加算更新
                    new_abundance = existing[1] + abundance
                    self.conn.execute("""
                        UPDATE occurrences SET abundance = ?
                        WHERE id = ?
                    """, (new_abundance, existing[0]))
                    logger.info(f"↑ Updated: {species_name} at {site_name} ({existing[1]} → {new_abundance})")
                else:
                    # 新規登録
                    self.conn.execute("""
                        INSERT INTO occurrences 
                        (site_id, species_id, method_id, abundance, unit)
                        VALUES (?, ?, ?, ?, ?)
                    """, (site_id, species_id, method_id, abundance, unit))
                    logger.info(f"✓ {species_name} at {site_name}")
                
                self.conn.commit()
                
            except Exception as e:
                self.error_log.append(f"Row {idx}: {e}")
                logger.error(f"Row {idx}: {e}")
    
    def save_error_log(self, output_path: str = "import_errors.log"):
        """エラーログをファイル出力"""
        if self.error_log:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.error_log))
            logger.warning(f"Errors logged to {output_path}")
    
    def close(self):
        self.conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import CSV data to Ant Research DB')
    parser.add_argument('--db', default='ant_research.db', help='Database file path')
    parser.add_argument('--data', default='./csv_data', help='CSV directory')
    args = parser.parse_args()
    
    data_dir = Path(args.data)
    importer = AntDatabaseImporter(args.db)
    
    try:
        # 順序重要: species → research → records
        if (data_dir / 'species.csv').exists():
            importer.import_species(data_dir / 'species.csv')
        
        if (data_dir / 'research.csv').exists():
            importer.import_research(data_dir / 'research.csv')
        
        if (data_dir / 'records.csv').exists():
            importer.import_records(data_dir / 'records.csv')
        
        importer.save_error_log()
        logger.info("✅ Import completed!")
        
    finally:
        importer.close()


if __name__ == '__main__':
    main()
