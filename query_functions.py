#!/usr/bin/env python3
"""
アリ類研究データベース クエリ関数集
"""

import sqlite3
import pandas as pd
from typing import List, Dict, Any


class AntDatabaseQuery:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def search_species(self, name: str) -> List[Dict[str, Any]]:
        """種名検索 (部分一致)"""
        query = """
        SELECT DISTINCT
            s.id,
            s.scientific_name,
            s.japanese_name,
            s.subfamily,
            s.body_len_mm,
            s.red_list,
            GROUP_CONCAT(DISTINCT sy.name, '; ') AS synonyms
        FROM species s
        LEFT JOIN species_synonyms sy ON s.id = sy.species_id
        WHERE s.scientific_name LIKE ? 
           OR s.japanese_name LIKE ?
           OR sy.name LIKE ?
        GROUP BY s.id
        ORDER BY s.japanese_name
        """
        pattern = f"%{name}%"
        cursor = self.conn.execute(query, (pattern, pattern, pattern))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_sympatric_species(self, species_id: int, min_sites: int = 1) -> pd.DataFrame:
        """同所的に出現した種の一覧"""
        query = """
        SELECT DISTINCT
            s.id,
            s.scientific_name,
            s.japanese_name,
            s.subfamily,
            COUNT(DISTINCT o2.site_id) AS co_occurrence_sites,
            GROUP_CONCAT(DISTINCT ss.site_name, ', ') AS sites
        FROM occurrences o1
        JOIN occurrences o2 ON o1.site_id = o2.site_id
        JOIN species s ON o2.species_id = s.id
        JOIN survey_sites ss ON o1.site_id = ss.id
        WHERE o1.species_id = ?
          AND o2.species_id != ?
        GROUP BY s.id
        HAVING co_occurrence_sites >= ?
        ORDER BY co_occurrence_sites DESC, s.japanese_name
        """
        return pd.read_sql_query(query, self.conn, params=(species_id, species_id, min_sites))
    
    def get_habitats(self, species_id: int) -> pd.DataFrame:
        """生息環境の統計"""
        query = """
        SELECT 
            et.name AS environment,
            COUNT(DISTINCT ss.id) AS site_count,
            SUM(o.abundance) AS total_individuals,
            AVG(o.abundance) AS avg_abundance,
            MIN(ss.elevation_m) AS min_elevation,
            MAX(ss.elevation_m) AS max_elevation,
            GROUP_CONCAT(DISTINCT ss.site_name, ', ') AS sites
        FROM occurrences o
        JOIN survey_sites ss ON o.site_id = ss.id
        LEFT JOIN environment_types et ON ss.env_type_id = et.id
        WHERE o.species_id = ?
        GROUP BY et.id
        ORDER BY site_count DESC
        """
        return pd.read_sql_query(query, self.conn, params=(species_id,))
    
    def get_research_list(self, species_id: int) -> pd.DataFrame:
        """記録された研究の一覧"""
        query = """
        SELECT DISTINCT
            r.id,
            r.title,
            r.author,
            r.year,
            r.doi,
            COUNT(DISTINCT ss.id) AS sites_count,
            SUM(o.abundance) AS total_records
        FROM occurrences o
        JOIN survey_sites ss ON o.site_id = ss.id
        JOIN research r ON ss.research_id = r.id
        WHERE o.species_id = ?
        GROUP BY r.id
        ORDER BY r.year DESC, r.title
        """
        return pd.read_sql_query(query, self.conn, params=(species_id,))
    
    def get_occurrence_details(self, species_id: int) -> pd.DataFrame:
        """詳細な出現記録"""
        query = """
        SELECT 
            r.title AS research,
            r.year,
            ss.site_name,
            ss.survey_date,
            ss.latitude,
            ss.longitude,
            ss.elevation_m,
            et.name AS environment,
            m.name AS method,
            o.abundance,
            o.unit
        FROM occurrences o
        JOIN survey_sites ss ON o.site_id = ss.id
        JOIN research r ON ss.research_id = r.id
        LEFT JOIN environment_types et ON ss.env_type_id = et.id
        LEFT JOIN methods m ON o.method_id = m.id
        WHERE o.species_id = ?
        ORDER BY r.year DESC, ss.survey_date DESC
        """
        return pd.read_sql_query(query, self.conn, params=(species_id,))
    
    def get_site_species_list(self, site_id: int) -> pd.DataFrame:
        """特定地点の種リスト"""
        query = """
        SELECT 
            s.scientific_name,
            s.japanese_name,
            s.subfamily,
            o.abundance,
            o.unit,
            m.name AS method
        FROM occurrences o
        JOIN species s ON o.species_id = s.id
        LEFT JOIN methods m ON o.method_id = m.id
        WHERE o.site_id = ?
        ORDER BY s.japanese_name
        """
        return pd.read_sql_query(query, self.conn, params=(site_id,))
    
    def statistics_summary(self) -> Dict[str, int]:
        """データベース統計"""
        stats = {}
        stats['total_species'] = self.conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
        stats['total_research'] = self.conn.execute("SELECT COUNT(*) FROM research").fetchone()[0]
        stats['total_sites'] = self.conn.execute("SELECT COUNT(*) FROM survey_sites").fetchone()[0]
        stats['total_occurrences'] = self.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]
        
        # 最新研究年
        latest = self.conn.execute("SELECT MAX(year) FROM research").fetchone()[0]
        stats['latest_research_year'] = latest if latest else 0
        
        return stats
    
    def close(self):
        self.conn.close()


# ========== 使用例 ==========
if __name__ == '__main__':
    db = AntDatabaseQuery('ant_research.db')
    
    # 種検索
    results = db.search_species('クロヤマ')
    if results:
        species_id = results[0]['id']
        print(f"Found: {results[0]['japanese_name']} ({results[0]['scientific_name']})\n")
        
        # 同所種
        print("=== 同所的種 ===")
        print(db.get_sympatric_species(species_id))
        
        # 生息環境
        print("\n=== 生息環境 ===")
        print(db.get_habitats(species_id))
        
        # 研究一覧
        print("\n=== 記録研究 ===")
        print(db.get_research_list(species_id))
    
    # 統計
    print("\n=== データベース統計 ===")
    print(db.statistics_summary())
    
    db.close()
