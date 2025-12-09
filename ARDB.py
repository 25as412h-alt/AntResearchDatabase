import sqlite3
import os
import logging
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
import hashlib
import unicodedata
import json
from pathlib import Path
from datetime import datetime
import csv

# ユーティリティモジュールのインポート
from database.db_utils import (
    normalize_text,
    generate_unique_hash,
    parse_date,
    read_csv_file,
    write_csv_file,
    validate_required_fields,
    parse_coordinate,
    parse_int,
    parse_float
)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ardb.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ARDB')

class AntResearchDB:
    """
    アリ類研究データベース管理クラス
    
    このクラスは、アリ類の研究データを管理するためのデータベース操作を提供します。
    データベースの初期化、テーブル作成、データの追加・取得・更新・削除などの機能を提供します。
    """
    
    def __init__(self, db_path: str = "database/ant_research.db"):
        """
        データベース接続を初期化する
        
        Args:
            db_path (str): データベースファイルのパス。デフォルトは'database/ant_research.db'
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_database_dir()
        self._connect()
        self._initialize_database()
    
    def _ensure_database_dir(self) -> None:
        """データベースディレクトリが存在することを確認し、なければ作成する"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
    
    def _connect(self) -> None:
        """データベースに接続する"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # 外部キー制約を有効化
            self.conn.execute("PRAGMA foreign_keys = ON;")
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def _initialize_database(self) -> None:
        """データベースを初期化し、必要なテーブルを作成する"""
        try:
            cursor = self.conn.cursor()
            
            # マスターテーブルの作成
            self._create_master_tables(cursor)
            
            # 研究データテーブルの作成
            self._create_research_tables(cursor)
            
            # 観測データテーブルの作成
            self._create_observation_tables(cursor)
            
            # 全文検索用の仮想テーブル作成
            self._create_fts_tables(cursor)
            
            self.conn.commit()
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            self.conn.rollback()
            raise
    
    def _create_master_tables(self, cursor: sqlite3.Cursor) -> None:
        """マスターテーブルを作成する"""
        # 生物種マスターテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS species (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scientific_name TEXT UNIQUE NOT NULL,
            japanese_name TEXT NOT NULL,
            subfamily TEXT,
            body_len_min REAL,
            body_len_max REAL,
            dist_text TEXT,
            elev_min INTEGER,
            elev_max INTEGER,
            red_list TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 生物種シノニムテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS species_synonyms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('scientific', 'japanese', 'synonym')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
            UNIQUE(species_id, name)
        )
        ''')
        
        # 環境タイプマスターテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS environment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 調査手法マスターテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 季節マスターテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 単位マスターテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    def _create_research_tables(self, cursor: sqlite3.Cursor) -> None:
        """研究データ関連のテーブルを作成する"""
        # 研究テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doi TEXT UNIQUE,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            year INTEGER NOT NULL,
            unique_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (year > 0)
        )
        ''')
        
        # 研究テキストテーブル（全文検索用）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_texts (
            research_id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            FOREIGN KEY (research_id) REFERENCES research(id) ON DELETE CASCADE
        )
        ''')
    
    def _create_observation_tables(self, cursor: sqlite3.Cursor) -> None:
        """観測データ関連のテーブルを作成する"""
        # 調査地点テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_id INTEGER NOT NULL,
            site_name TEXT NOT NULL,
            date_start TEXT NOT NULL,
            environment_type_id INTEGER,
            season_id INTEGER,
            latitude REAL,
            longitude REAL,
            elevation INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (research_id) REFERENCES research(id) ON DELETE CASCADE,
            FOREIGN KEY (environment_type_id) REFERENCES environment_types(id),
            FOREIGN KEY (season_id) REFERENCES seasons(id),
            CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
            CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),
            CHECK (elevation IS NULL OR elevation > -500),
            UNIQUE(research_id, site_name, date_start, latitude, longitude, elevation)
        )
        ''')
        
        # 出現記録テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            species_id INTEGER NOT NULL,
            method_id INTEGER,
            unit_id INTEGER,
            abundance INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (site_id) REFERENCES survey_sites(id) ON DELETE CASCADE,
            FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE RESTRICT,
            FOREIGN KEY (method_id) REFERENCES methods(id),
            FOREIGN KEY (unit_id) REFERENCES units(id),
            CHECK (abundance >= 0),
            UNIQUE(site_id, species_id, method_id, unit_id)
        )
        ''')
    
    def _create_fts_tables(self, cursor: sqlite3.Cursor) -> None:
        """全文検索用の仮想テーブルを作成する"""
        # 研究テキストの全文検索用仮想テーブル
        cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS research_texts_fts USING fts5(
            content,
            content='research_texts',
            content_rowid='research_id',
            tokenize='unicode61 remove_diacritics 1'
        )
        ''')
        
        # トリガー: research_textsに挿入時にFTSテーブルも更新
        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS research_texts_ai AFTER INSERT ON research_texts
        BEGIN
            INSERT INTO research_texts_fts(rowid, content) VALUES (new.research_id, new.content);
        END;
        ''')
        
        # トリガー: research_textsを更新時にFTSテーブルも更新
        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS research_texts_au AFTER UPDATE ON research_texts
        BEGIN
            INSERT INTO research_texts_fts(research_texts_fts, rowid, content) 
            VALUES ('delete', old.research_id, old.content);
            INSERT INTO research_texts_fts(rowid, content) 
            VALUES (new.research_id, new.content);
        END;
        ''')
        
        # トリガー: research_textsを削除時にFTSテーブルからも削除
        cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS research_texts_ad AFTER DELETE ON research_texts
        BEGIN
            INSERT INTO research_texts_fts(research_texts_fts, rowid, content) 
            VALUES ('delete', old.research_id, old.content);
        END;
        ''')
    
    def _generate_unique_hash(self, title: str, author: str, year: int) -> str:
        """研究論文の一意のハッシュを生成する"""
        hash_input = f"{title}{author}{year}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """テキストを正規化する（全角・半角、大文字・小文字の統一など）"""
        if not text:
            return ""
        # NFKC正規化（全角英数字→半角、全角スペース→半角スペースなど）
        normalized = unicodedata.normalize('NFKC', text.strip())
        # 連続する空白を1つに置換
        normalized = ' '.join(normalized.split())
        return normalized
    
    def close(self) -> None:
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        """with文での使用をサポート"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """with文終了時にリソースを解放"""
        self.close()
    
    # ============================================
    # 生物種関連のメソッド
    # ============================================
    
    def add_species(self, scientific_name: str, japanese_name: str, **kwargs) -> Optional[int]:
        """
        生物種を追加する
        
        Args:
            scientific_name (str): 学名
            japanese_name (str): 和名
            **kwargs: その他の属性（subfamily, body_len_min, body_len_max, dist_text, elev_min, elev_max, red_list）
            
        Returns:
            Optional[int]: 追加した生物種のID（失敗した場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 必須フィールドの検証
            if not scientific_name or not japanese_name:
                logger.error("学名と和名は必須です")
                return None
            
            # 既存の学名がないか確認
            cursor.execute("SELECT id FROM species WHERE scientific_name = ?", (scientific_name,))
            if cursor.fetchone():
                logger.warning(f"既に登録されている学名です: {scientific_name}")
                return None
            
            # 生物種を追加
            cursor.execute('''
                INSERT INTO species (
                    scientific_name, japanese_name, subfamily, 
                    body_len_min, body_len_max, dist_text, 
                    elev_min, elev_max, red_list
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scientific_name, japanese_name, kwargs.get('subfamily'),
                kwargs.get('body_len_min'), kwargs.get('body_len_max'), kwargs.get('dist_text'),
                kwargs.get('elev_min'), kwargs.get('elev_max'), kwargs.get('red_list')
            ))
            
            species_id = cursor.lastrowid
            
            # 学名と和名をシノニムとして登録
            self._add_synonym(species_id, scientific_name, 'scientific')
            self._add_synonym(species_id, japanese_name, 'japanese')
            
            # シノニムがあれば登録
            synonyms = kwargs.get('synonyms', [])
            if isinstance(synonyms, str):
                synonyms = [s.strip() for s in synonyms.split(',') if s.strip()]
            
            for syn in synonyms:
                self._add_synonym(species_id, syn, 'synonym')
            
            self.conn.commit()
            logger.info(f"生物種を追加しました: {scientific_name} (ID: {species_id})")
            return species_id
            
        except sqlite3.Error as e:
            logger.error(f"生物種の追加中にエラーが発生しました: {e}")
            self.conn.rollback()
            return None
    
    def _add_synonym(self, species_id: int, name: str, syn_type: str) -> bool:
        """生物種のシノニムを追加する（内部メソッド）"""
        if not name or not name.strip():
            return False
            
        try:
            normalized = normalize_text(name)
            cursor = self.conn.cursor()
            
            # 既に登録されていないか確認
            cursor.execute(
                "SELECT id FROM species_synonyms WHERE name_normalized = ?", 
                (normalized,)
            )
            if cursor.fetchone():
                return False
                
            cursor.execute('''
                INSERT INTO species_synonyms (species_id, name, name_normalized, type)
                VALUES (?, ?, ?, ?)
            ''', (species_id, name, normalized, syn_type))
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"シノニムの追加中にエラーが発生しました: {e}")
            return False
    
    def search_species(self, query: str, exact_match: bool = False) -> List[Dict[str, Any]]:
        """
        生物種を検索する
        
        Args:
            query (str): 検索クエリ（学名、和名、シノニムのいずれか）
            exact_match (bool): 完全一致で検索するかどうか
            
        Returns:
            List[Dict[str, Any]]: 検索結果のリスト
        """
        if not query:
            return []
            
        try:
            cursor = self.conn.cursor()
            normalized = normalize_text(query)
            
            if exact_match:
                # 完全一致検索
                cursor.execute('''
                    SELECT s.* FROM species s
                    JOIN species_synonyms ss ON s.id = ss.species_id
                    WHERE ss.name_normalized = ?
                    GROUP BY s.id
                    ORDER BY 
                        CASE 
                            WHEN s.scientific_name = ? THEN 1
                            WHEN s.japanese_name = ? THEN 2
                            ELSE 3
                        END,
                        s.scientific_name
                ''', (normalized, query, query))
            else:
                # 部分一致検索
                like_pattern = f'%{normalized}%'
                cursor.execute('''
                    SELECT s.* FROM species s
                    JOIN species_synonyms ss ON s.id = ss.species_id
                    WHERE ss.name_normalized LIKE ?
                    GROUP BY s.id
                    ORDER BY 
                        CASE 
                            WHEN s.scientific_name = ? THEN 1
                            WHEN s.japanese_name = ? THEN 2
                            WHEN s.scientific_name LIKE ? THEN 3
                            WHEN s.japanese_name LIKE ? THEN 4
                            ELSE 5
                        END,
                        s.scientific_name
                ''', (like_pattern, query, query, like_pattern, like_pattern))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"生物種の検索中にエラーが発生しました: {e}")
            return []
    
    def get_species(self, species_id: int) -> Optional[Dict[str, Any]]:
        """
        生物種の詳細情報を取得する
        
        Args:
            species_id (int): 生物種ID
            
        Returns:
            Optional[Dict[str, Any]]: 生物種の詳細情報（見つからない場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 基本情報を取得
            cursor.execute('''
                SELECT * FROM species 
                WHERE id = ?
            ''', (species_id,))
            
            species = cursor.fetchone()
            if not species:
                return None
            
            # 辞書に変換
            result = dict(species)
            
            # シノニムを取得
            cursor.execute('''
                SELECT name, type FROM species_synonyms
                WHERE species_id = ?
                ORDER BY type, name
            ''', (species_id,))
            
            result['synonyms'] = [dict(row) for row in cursor.fetchall()]
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"生物種情報の取得中にエラーが発生しました: {e}")
            return None
    
    def update_species(self, species_id: int, **kwargs) -> bool:
        """
        生物種の情報を更新する
        
        Args:
            species_id (int): 更新する生物種のID
            **kwargs: 更新するフィールドと値
            
        Returns:
            bool: 更新が成功したかどうか
        """
        if not kwargs:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # 更新可能なフィールド
            allowed_fields = {
                'scientific_name', 'japanese_name', 'subfamily',
                'body_len_min', 'body_len_max', 'dist_text',
                'elev_min', 'elev_max', 'red_list'
            }
            
            # 更新フィールドをフィルタリング
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not update_fields:
                logger.warning("有効な更新フィールドが指定されていません")
                return False
            
            # 学名が変更される場合は重複チェック
            if 'scientific_name' in update_fields:
                cursor.execute(
                    "SELECT id FROM species WHERE scientific_name = ? AND id != ?",
                    (update_fields['scientific_name'], species_id)
                )
                if cursor.fetchone():
                    logger.error(f"既に登録されている学名です: {update_fields['scientific_name']}")
                    return False
            
            # 更新クエリを構築
            set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
            values = list(update_fields.values())
            values.append(species_id)
            
            query = f"UPDATE species SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cursor.execute(query, values)
            
            # シノニムの更新
            if 'synonyms' in kwargs:
                # 既存のシノニムを削除（学名と和名は除く）
                cursor.execute('''
                    DELETE FROM species_synonyms 
                    WHERE species_id = ? AND type = 'synonym'
                ''', (species_id,))
                
                # 新しいシノニムを追加
                synonyms = kwargs['synonyms']
                if isinstance(synonyms, str):
                    synonyms = [s.strip() for s in synonyms.split(',') if s.strip()]
                
                for syn in synonyms:
                    self._add_synonym(species_id, syn, 'synonym')
            
            self.conn.commit()
            logger.info(f"生物種を更新しました: ID {species_id}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"生物種の更新中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    def delete_species(self, species_id: int) -> bool:
        """
        生物種を削除する（関連する出現記録も削除される）
        
        Args:
            species_id (int): 削除する生物種のID
            
        Returns:
            bool: 削除が成功したかどうか
        """
        try:
            cursor = self.conn.cursor()
            
            # 生物種の存在確認
            cursor.execute("SELECT scientific_name FROM species WHERE id = ?", (species_id,))
            species = cursor.fetchone()
            
            if not species:
                logger.error(f"生物種が見つかりません: ID {species_id}")
                return False
            
            # 削除を実行（外部キー制約により関連する出現記録も削除される）
            cursor.execute("DELETE FROM species WHERE id = ?", (species_id,))
            
            self.conn.commit()
            logger.info(f"生物種を削除しました: {species['scientific_name']} (ID: {species_id})")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"生物種の削除中に整合性エラーが発生しました: {e}")
            self.conn.rollback()
            return False
        except sqlite3.Error as e:
            logger.error(f"生物種の削除中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    # ============================================
    # 研究論文関連のメソッド
    # ============================================
    
    def add_research(self, title: str, author: str, year: int, doi: str = None, 
                    content: str = None, **kwargs) -> Optional[int]:
        """
        研究論文を追加する
        
        Args:
            title (str): 論文タイトル
            author (str): 著者名
            year (int): 出版年
            doi (str, optional): DOI（Digital Object Identifier）
            content (str, optional): 論文の全文テキスト
            **kwargs: その他の属性
            
        Returns:
            Optional[int]: 追加した研究論文のID（失敗した場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 必須フィールドの検証
            if not title or not author or not year:
                logger.error("タイトル、著者、出版年は必須です")
                return None
            
            # 一意のハッシュを生成
            unique_hash = generate_unique_hash(title, author, year)
            
            # DOIまたはハッシュで既存の論文を確認
            if doi:
                cursor.execute("SELECT id FROM research WHERE doi = ?", (doi,))
            else:
                cursor.execute("SELECT id FROM research WHERE unique_hash = ?", (unique_hash,))
                
            existing = cursor.fetchone()
            if existing:
                logger.warning(f"既に登録されている研究論文です: ID {existing['id']}")
                return None
            
            # 研究論文を追加
            cursor.execute('''
                INSERT INTO research (title, author, year, doi, unique_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, author, year, doi, unique_hash))
            
            research_id = cursor.lastrowid
            
            # 全文テキストがあれば追加
            if content:
                cursor.execute('''
                    INSERT INTO research_texts (research_id, content)
                    VALUES (?, ?)
                ''', (research_id, content))
            
            self.conn.commit()
            logger.info(f"研究論文を追加しました: {title} (ID: {research_id})")
            return research_id
            
        except sqlite3.Error as e:
            logger.error(f"研究論文の追加中にエラーが発生しました: {e}")
            self.conn.rollback()
            return None
    
    def search_research(self, query: str = None, author: str = None, 
                       year_from: int = None, year_to: int = None,
                       limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        研究論文を検索する
        
        Args:
            query (str, optional): 検索クエリ（タイトル、著者、全文検索）
            author (str, optional): 著者名で絞り込み
            year_from (int, optional): 出版年の開始年
            year_to (int, optional): 出版年の終了年
            limit (int): 取得する最大件数
            offset (int): 取得開始位置
            
        Returns:
            List[Dict[str, Any]]: 検索結果のリスト
        """
        try:
            cursor = self.conn.cursor()
            params = []
            conditions = []
            
            # 検索条件を構築
            if query:
                # 全文検索を使用
                conditions.append("""
                    r.id IN (
                        SELECT rowid FROM research_texts_fts 
                        WHERE research_texts_fts MATCH ?
                    )
                    OR r.title LIKE ? 
                    OR r.author LIKE ?
                """)
                params.extend([query, f'%{query}%', f'%{query}%'])
            
            if author:
                conditions.append("r.author LIKE ?")
                params.append(f'%{author}%')
            
            if year_from is not None:
                conditions.append("r.year >= ?")
                params.append(year_from)
            
            if year_to is not None:
                conditions.append("r.year <= ?")
                params.append(year_to)
            
            # クエリを構築
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT r.*, 
                       (SELECT COUNT(*) FROM survey_sites WHERE research_id = r.id) as site_count
                FROM research r
                WHERE {where_clause}
                ORDER BY r.year DESC, r.author, r.title
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"研究論文の検索中にエラーが発生しました: {e}")
            return []
    
    def get_research(self, research_id: int) -> Optional[Dict[str, Any]]:
        """
        研究論文の詳細を取得する
        
        Args:
            research_id (int): 研究論文のID
            
        Returns:
            Optional[Dict[str, Any]]: 研究論文の詳細情報（見つからない場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 基本情報を取得
            cursor.execute('''
                SELECT r.*, 
                       (SELECT content FROM research_texts WHERE research_id = r.id) as content
                FROM research r
                WHERE r.id = ?
            ''', (research_id,))
            
            research = cursor.fetchone()
            if not research:
                return None
            
            # 調査地点の数を取得
            cursor.execute('''
                SELECT COUNT(*) as site_count 
                FROM survey_sites 
                WHERE research_id = ?
            ''', (research_id,))
            
            result = dict(research)
            result['site_count'] = cursor.fetchone()['site_count']
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"研究論文の取得中にエラーが発生しました: {e}")
            return None
    
    def update_research(self, research_id: int, **kwargs) -> bool:
        """
        研究論文の情報を更新する
        
        Args:
            research_id (int): 更新する研究論文のID
            **kwargs: 更新するフィールドと値
            
        Returns:
            bool: 更新が成功したかどうか
        """
        if not kwargs:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # 更新可能なフィールド
            allowed_fields = {'title', 'author', 'year', 'doi', 'content'}
            
            # 更新フィールドをフィルタリング
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not update_fields:
                logger.warning("有効な更新フィールドが指定されていません")
                return False
            
            # 研究論文の存在確認
            cursor.execute("SELECT id FROM research WHERE id = ?", (research_id,))
            if not cursor.fetchone():
                logger.error(f"研究論文が見つかりません: ID {research_id}")
                return False
            
            # ハッシュの再計算が必要なフィールドが含まれているか確認
            if any(field in update_fields for field in ['title', 'author', 'year']):
                # 現在の値を取得
                cursor.execute("SELECT title, author, year FROM research WHERE id = ?", (research_id,))
                current = cursor.fetchone()
                
                # 新しい値でハッシュを再計算
                title = update_fields.get('title', current['title'])
                author = update_fields.get('author', current['author'])
                year = update_fields.get('year', current['year'])
                
                unique_hash = generate_unique_hash(title, author, year)
                
                # ハッシュの重複チェック
                cursor.execute(
                    "SELECT id FROM research WHERE unique_hash = ? AND id != ?",
                    (unique_hash, research_id)
                )
                if cursor.fetchone():
                    logger.error("更新後の情報と重複する研究論文が既に存在します")
                    return False
                
                update_fields['unique_hash'] = unique_hash
            
            # 研究論文の基本情報を更新
            if any(field in update_fields for field in ['title', 'author', 'year', 'doi']):
                # 更新するフィールドを抽出
                research_fields = {k: v for k, v in update_fields.items() 
                                 if k in ['title', 'author', 'year', 'doi', 'unique_hash']}
                
                set_clause = ", ".join(f"{k} = ?" for k in research_fields.keys())
                values = list(research_fields.values())
                values.append(research_id)
                
                query = f"UPDATE research SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, values)
            
            # 全文テキストを更新または追加
            if 'content' in update_fields:
                cursor.execute('''
                    INSERT OR REPLACE INTO research_texts (research_id, content)
                    VALUES (?, ?)
                ''', (research_id, update_fields['content']))
            
            self.conn.commit()
            logger.info(f"研究論文を更新しました: ID {research_id}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"研究論文の更新中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    def delete_research(self, research_id: int) -> bool:
        """
        研究論文を削除する（関連する調査地点や出現記録も削除される）
        
        Args:
            research_id (int): 削除する研究論文のID
            
        Returns:
            bool: 削除が成功したかどうか
        """
        try:
            cursor = self.conn.cursor()
            
            # 研究論文の存在確認
            cursor.execute("SELECT title FROM research WHERE id = ?", (research_id,))
            research = cursor.fetchone()
            
            if not research:
                logger.error(f"研究論文が見つかりません: ID {research_id}")
                return False
            
            # 削除を実行（外部キー制約により関連する調査地点や出現記録も削除される）
            cursor.execute("DELETE FROM research WHERE id = ?", (research_id,))
            
            self.conn.commit()
            logger.info(f"研究論文を削除しました: {research['title']} (ID: {research_id})")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"研究論文の削除中に整合性エラーが発生しました: {e}")
            self.conn.rollback()
            return False
        except sqlite3.Error as e:
            logger.error(f"研究論文の削除中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    # ============================================
    # 調査地点関連のメソッド
    # ============================================
    
    def add_survey_site(self, research_id: int, site_name: str, date_start: str, 
                       environment_type_id: int = None, season_id: int = None,
                       latitude: float = None, longitude: float = None, 
                       elevation: int = None, **kwargs) -> Optional[int]:
        """
        調査地点を追加する
        
        Args:
            research_id (int): 関連する研究論文のID
            site_name (str): 調査地点名
            date_start (str): 調査開始日（YYYY-MM-DD形式）
            environment_type_id (int, optional): 環境タイプID
            season_id (int, optional): 季節ID
            latitude (float, optional): 緯度（-90〜90）
            longitude (float, optional): 経度（-180〜180）
            elevation (int, optional): 標高（メートル）
            **kwargs: その他の属性
            
        Returns:
            Optional[int]: 追加した調査地点のID（失敗した場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 必須フィールドの検証
            if not site_name or not date_start:
                logger.error("調査地点名と調査開始日は必須です")
                return None
            
            # 研究論文の存在確認
            cursor.execute("SELECT id FROM research WHERE id = ?", (research_id,))
            if not cursor.fetchone():
                logger.error(f"研究論文が見つかりません: ID {research_id}")
                return None
            
            # 日付の検証
            parsed_date = parse_date(date_start)
            if not parsed_date:
                logger.error(f"無効な日付形式です: {date_start}")
                return None
            
            # 座標の検証
            if latitude is not None and not (-90 <= float(latitude) <= 90):
                logger.error(f"緯度の値が範囲外です: {latitude}")
                return None
                
            if longitude is not None and not (-180 <= float(longitude) <= 180):
                logger.error(f"経度の値が範囲外です: {longitude}")
                return None
            
            # 調査地点を追加
            cursor.execute('''
                INSERT INTO survey_sites (
                    research_id, site_name, date_start, environment_type_id,
                    season_id, latitude, longitude, elevation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                research_id, site_name, parsed_date, environment_type_id,
                season_id, latitude, longitude, elevation
            ))
            
            site_id = cursor.lastrowid
            
            self.conn.commit()
            logger.info(f"調査地点を追加しました: {site_name} (ID: {site_id})")
            return site_id
            
        except (ValueError, TypeError) as e:
            logger.error(f"無効なパラメータが指定されました: {e}")
            self.conn.rollback()
            return None
        except sqlite3.Error as e:
            logger.error(f"調査地点の追加中にエラーが発生しました: {e}")
            self.conn.rollback()
            return None
    
    def get_survey_sites(self, research_id: int = None, 
                        environment_type_id: int = None,
                        season_id: int = None,
                        limit: int = 100, 
                        offset: int = 0) -> List[Dict[str, Any]]:
        """
        調査地点の一覧を取得する
        
        Args:
            research_id (int, optional): 研究論文IDで絞り込み
            environment_type_id (int, optional): 環境タイプIDで絞り込み
            season_id (int, optional): 季節IDで絞り込み
            limit (int): 取得する最大件数
            offset (int): 取得開始位置
            
        Returns:
            List[Dict[str, Any]]: 調査地点のリスト
        """
        try:
            cursor = self.conn.cursor()
            params = []
            conditions = []
            
            # 検索条件を構築
            if research_id is not None:
                conditions.append("ss.research_id = ?")
                params.append(research_id)
            
            if environment_type_id is not None:
                conditions.append("ss.environment_type_id = ?")
                params.append(environment_type_id)
            
            if season_id is not None:
                conditions.append("ss.season_id = ?")
                params.append(season_id)
            
            # クエリを構築
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT ss.*, 
                       r.title as research_title,
                       r.author as research_author,
                       r.year as research_year,
                       et.name as environment_type_name,
                       s.name as season_name,
                       (SELECT COUNT(*) FROM occurrences WHERE site_id = ss.id) as occurrence_count
                FROM survey_sites ss
                LEFT JOIN research r ON ss.research_id = r.id
                LEFT JOIN environment_types et ON ss.environment_type_id = et.id
                LEFT JOIN seasons s ON ss.season_id = s.id
                WHERE {where_clause}
                ORDER BY ss.date_start DESC, ss.site_name
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # 座標が存在する場合は辞書に追加
                if result['latitude'] is not None and result['longitude'] is not None:
                    result['coordinates'] = {
                        'latitude': result.pop('latitude'),
                        'longitude': result.pop('longitude')
                    }
                results.append(result)
            
            return results
            
        except sqlite3.Error as e:
            logger.error(f"調査地点の取得中にエラーが発生しました: {e}")
            return []
    
    def get_survey_site(self, site_id: int) -> Optional[Dict[str, Any]]:
        """
        調査地点の詳細を取得する
        
        Args:
            site_id (int): 調査地点のID
            
        Returns:
            Optional[Dict[str, Any]]: 調査地点の詳細情報（見つからない場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 基本情報を取得
            cursor.execute('''
                SELECT ss.*, 
                       r.title as research_title,
                       r.author as research_author,
                       r.year as research_year,
                       et.name as environment_type_name,
                       s.name as season_name
                FROM survey_sites ss
                LEFT JOIN research r ON ss.research_id = r.id
                LEFT JOIN environment_types et ON ss.environment_type_id = et.id
                LEFT JOIN seasons s ON ss.season_id = s.id
                WHERE ss.id = ?
            ''', (site_id,))
            
            site = cursor.fetchone()
            if not site:
                return None
            
            result = dict(site)
            
            # 座標が存在する場合は辞書に追加
            if result['latitude'] is not None and result['longitude'] is not None:
                result['coordinates'] = {
                    'latitude': result.pop('latitude'),
                    'longitude': result.pop('longitude')
                }
            
            # 出現記録の数を取得
            cursor.execute('''
                SELECT COUNT(*) as count 
                FROM occurrences 
                WHERE site_id = ?
            ''', (site_id,))
            
            result['occurrence_count'] = cursor.fetchone()['count']
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"調査地点の取得中にエラーが発生しました: {e}")
            return None
    
    def update_survey_site(self, site_id: int, **kwargs) -> bool:
        """
        調査地点の情報を更新する
        
        Args:
            site_id (int): 更新する調査地点のID
            **kwargs: 更新するフィールドと値
            
        Returns:
            bool: 更新が成功したかどうか
        """
        if not kwargs:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # 更新可能なフィールド
            allowed_fields = {
                'site_name', 'date_start', 'environment_type_id',
                'season_id', 'latitude', 'longitude', 'elevation'
            }
            
            # 更新フィールドをフィルタリング
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not update_fields:
                logger.warning("有効な更新フィールドが指定されていません")
                return False
            
            # 調査地点の存在確認
            cursor.execute("SELECT id FROM survey_sites WHERE id = ?", (site_id,))
            if not cursor.fetchone():
                logger.error(f"調査地点が見つかりません: ID {site_id}")
                return False
            
            # 日付の検証
            if 'date_start' in update_fields:
                parsed_date = parse_date(update_fields['date_start'])
                if not parsed_date:
                    logger.error(f"無効な日付形式です: {update_fields['date_start']}")
                    return False
                update_fields['date_start'] = parsed_date
            
            # 座標の検証
            if 'latitude' in update_fields and update_fields['latitude'] is not None:
                try:
                    lat = float(update_fields['latitude'])
                    if not (-90 <= lat <= 90):
                        logger.error(f"緯度の値が範囲外です: {lat}")
                        return False
                except (ValueError, TypeError):
                    logger.error(f"無効な緯度の値です: {update_fields['latitude']}")
                    return False
            
            if 'longitude' in update_fields and update_fields['longitude'] is not None:
                try:
                    lon = float(update_fields['longitude'])
                    if not (-180 <= lon <= 180):
                        logger.error(f"経度の値が範囲外です: {lon}")
                        return False
                except (ValueError, TypeError):
                    logger.error(f"無効な経度の値です: {update_fields['longitude']}")
                    return False
            
            # 更新クエリを構築
            set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
            values = list(update_fields.values())
            values.append(site_id)
            
            query = f"UPDATE survey_sites SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cursor.execute(query, values)
            
            self.conn.commit()
            logger.info(f"調査地点を更新しました: ID {site_id}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"調査地点の更新中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    def delete_survey_site(self, site_id: int) -> bool:
        """
        調査地点を削除する（関連する出現記録も削除される）
        
        Args:
            site_id (int): 削除する調査地点のID
            
        Returns:
            bool: 削除が成功したかどうか
        """
        try:
            cursor = self.conn.cursor()
            
            # 調査地点の存在確認
            cursor.execute("SELECT site_name FROM survey_sites WHERE id = ?", (site_id,))
            site = cursor.fetchone()
            
            if not site:
                logger.error(f"調査地点が見つかりません: ID {site_id}")
                return False
            
            # 削除を実行（外部キー制約により関連する出現記録も削除される）
            cursor.execute("DELETE FROM survey_sites WHERE id = ?", (site_id,))
            
            self.conn.commit()
            logger.info(f"調査地点を削除しました: {site['site_name']} (ID: {site_id})")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"調査地点の削除中に整合性エラーが発生しました: {e}")
            self.conn.rollback()
            return False
        except sqlite3.Error as e:
            logger.error(f"調査地点の削除中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    # ============================================
    # 出現記録関連のメソッド
    # ============================================
    
    def add_occurrence(self, site_id: int, species_id: int, 
                      method_id: int = None, unit_id: int = None,
                      abundance: int = 1, notes: str = None) -> Optional[int]:
        """
        出現記録を追加する
        
        Args:
            site_id (int): 調査地点ID
            species_id (int): 生物種ID
            method_id (int, optional): 調査手法ID
            unit_id (int, optional): 単位ID
            abundance (int, optional): 個体数（デフォルト: 1）
            notes (str, optional): 備考
            
        Returns:
            Optional[int]: 追加した出現記録のID（失敗した場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 必須フィールドの検証
            if not site_id or not species_id:
                logger.error("調査地点IDと生物種IDは必須です")
                return None
            
            # 調査地点の存在確認
            cursor.execute("SELECT id FROM survey_sites WHERE id = ?", (site_id,))
            if not cursor.fetchone():
                logger.error(f"調査地点が見つかりません: ID {site_id}")
                return None
            
            # 生物種の存在確認
            cursor.execute("SELECT id FROM species WHERE id = ?", (species_id,))
            if not cursor.fetchone():
                logger.error(f"生物種が見つかりません: ID {species_id}")
                return None
            
            # 調査手法の存在確認
            if method_id is not None:
                cursor.execute("SELECT id FROM methods WHERE id = ?", (method_id,))
                if not cursor.fetchone():
                    logger.warning(f"調査手法が見つからないため、NULLとして登録します: ID {method_id}")
                    method_id = None
            
            # 単位の存在確認
            if unit_id is not None:
                cursor.execute("SELECT id FROM units WHERE id = ?", (unit_id,))
                if not cursor.fetchone():
                    logger.warning(f"単位が見つからないため、NULLとして登録します: ID {unit_id}")
                    unit_id = None
            
            # 個体数の検証
            try:
                abundance = int(abundance)
                if abundance < 0:
                    logger.error("個体数は0以上の整数を指定してください")
                    return None
            except (ValueError, TypeError):
                logger.error("個体数は数値で指定してください")
                return None
            
            # 出現記録を追加
            cursor.execute('''
                INSERT INTO occurrences (
                    site_id, species_id, method_id, unit_id, abundance, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (site_id, species_id, method_id, unit_id, abundance, notes))
            
            occurrence_id = cursor.lastrowid
            
            self.conn.commit()
            logger.info(f"出現記録を追加しました: ID {occurrence_id}")
            return occurrence_id
            
        except sqlite3.IntegrityError as e:
            logger.error(f"重複する出現記録が既に存在します: {e}")
            self.conn.rollback()
            return None
        except sqlite3.Error as e:
            logger.error(f"出現記録の追加中にエラーが発生しました: {e}")
            self.conn.rollback()
            return None
    
    def get_occurrences(self, site_id: int = None, species_id: int = None,
                       research_id: int = None, environment_type_id: int = None,
                       season_id: int = None, limit: int = 100, 
                       offset: int = 0) -> List[Dict[str, Any]]:
        """
        出現記録の一覧を取得する
        
        Args:
            site_id (int, optional): 調査地点IDで絞り込み
            species_id (int, optional): 生物種IDで絞り込み
            research_id (int, optional): 研究論文IDで絞り込み
            environment_type_id (int, optional): 環境タイプIDで絞り込み
            season_id (int, optional): 季節IDで絞り込み
            limit (int): 取得する最大件数
            offset (int): 取得開始位置
            
        Returns:
            List[Dict[str, Any]]: 出現記録のリスト
        """
        try:
            cursor = self.conn.cursor()
            params = []
            joins = ["occurrences o"]
            conditions = []
            
            # 結合と条件を構築
            joins.append("LEFT JOIN survey_sites ss ON o.site_id = ss.id")
            joins.append("LEFT JOIN species sp ON o.species_id = sp.id")
            joins.append("LEFT JOIN research r ON ss.research_id = r.id")
            joins.append("LEFT JOIN methods m ON o.method_id = m.id")
            joins.append("LEFT JOIN units u ON o.unit_id = u.id")
            joins.append("LEFT JOIN environment_types et ON ss.environment_type_id = et.id")
            joins.append("LEFT JOIN seasons s ON ss.season_id = s.id")
            
            if site_id is not None:
                conditions.append("o.site_id = ?")
                params.append(site_id)
            
            if species_id is not None:
                conditions.append("o.species_id = ?")
                params.append(species_id)
            
            if research_id is not None:
                conditions.append("ss.research_id = ?")
                params.append(research_id)
            
            if environment_type_id is not None:
                conditions.append("ss.environment_type_id = ?")
                params.append(environment_type_id)
            
            if season_id is not None:
                conditions.append("ss.season_id = ?")
                params.append(season_id)
            
            # クエリを構築
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT 
                    o.id, o.site_id, o.species_id, o.method_id, o.unit_id, 
                    o.abundance, o.notes, o.created_at, o.updated_at,
                    ss.site_name, ss.date_start,
                    sp.scientific_name, sp.japanese_name,
                    r.title as research_title, r.author as research_author, r.year as research_year,
                    m.name as method_name,
                    u.name as unit_name,
                    et.name as environment_type_name,
                    s.name as season_name
                FROM {" JOIN ".join(joins)}
                WHERE {where_clause}
                ORDER BY ss.date_start DESC, sp.scientific_name
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"出現記録の取得中にエラーが発生しました: {e}")
            return []
    
    def get_occurrence(self, occurrence_id: int) -> Optional[Dict[str, Any]]:
        """
        出現記録の詳細を取得する
        
        Args:
            occurrence_id (int): 出現記録のID
            
        Returns:
            Optional[Dict[str, Any]]: 出現記録の詳細情報（見つからない場合はNone）
        """
        try:
            cursor = self.conn.cursor()
            
            # 基本情報を取得
            cursor.execute('''
                SELECT 
                    o.*,
                    ss.site_name, ss.date_start, ss.latitude, ss.longitude, ss.elevation,
                    sp.scientific_name, sp.japanese_name,
                    r.id as research_id, r.title as research_title, r.author as research_author, r.year as research_year,
                    m.name as method_name,
                    u.name as unit_name,
                    et.name as environment_type_name,
                    s.name as season_name
                FROM occurrences o
                LEFT JOIN survey_sites ss ON o.site_id = ss.id
                LEFT JOIN species sp ON o.species_id = sp.id
                LEFT JOIN research r ON ss.research_id = r.id
                LEFT JOIN methods m ON o.method_id = m.id
                LEFT JOIN units u ON o.unit_id = u.id
                LEFT JOIN environment_types et ON ss.environment_type_id = et.id
                LEFT JOIN seasons s ON ss.season_id = s.id
                WHERE o.id = ?
            ''', (occurrence_id,))
            
            occurrence = cursor.fetchone()
            if not occurrence:
                return None
            
            result = dict(occurrence)
            
            # 座標が存在する場合は辞書に追加
            if result['latitude'] is not None and result['longitude'] is not None:
                result['coordinates'] = {
                    'latitude': result.pop('latitude'),
                    'longitude': result.pop('longitude')
                }
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"出現記録の取得中にエラーが発生しました: {e}")
            return None
    
    def update_occurrence(self, occurrence_id: int, **kwargs) -> bool:
        """
        出現記録の情報を更新する
        
        Args:
            occurrence_id (int): 更新する出現記録のID
            **kwargs: 更新するフィールドと値
            
        Returns:
            bool: 更新が成功したかどうか
        """
        if not kwargs:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # 更新可能なフィールド
            allowed_fields = {
                'species_id', 'method_id', 'unit_id', 'abundance', 'notes'
            }
            
            # 更新フィールドをフィルタリング
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not update_fields:
                logger.warning("有効な更新フィールドが指定されていません")
                return False
            
            # 出現記録の存在確認
            cursor.execute("SELECT id FROM occurrences WHERE id = ?", (occurrence_id,))
            if not cursor.fetchone():
                logger.error(f"出現記録が見つかりません: ID {occurrence_id}")
                return False
            
            # 生物種の存在確認
            if 'species_id' in update_fields:
                cursor.execute("SELECT id FROM species WHERE id = ?", (update_fields['species_id'],))
                if not cursor.fetchone():
                    logger.error(f"生物種が見つかりません: ID {update_fields['species_id']}")
                    return False
            
            # 調査手法の存在確認
            if 'method_id' in update_fields and update_fields['method_id'] is not None:
                cursor.execute("SELECT id FROM methods WHERE id = ?", (update_fields['method_id'],))
                if not cursor.fetchone():
                    logger.warning(f"調査手法が見つからないため、NULLとして更新します: ID {update_fields['method_id']}")
                    update_fields['method_id'] = None
            
            # 単位の存在確認
            if 'unit_id' in update_fields and update_fields['unit_id'] is not None:
                cursor.execute("SELECT id FROM units WHERE id = ?", (update_fields['unit_id'],))
                if not cursor.fetchone():
                    logger.warning(f"単位が見つからないため、NULLとして更新します: ID {update_fields['unit_id']}")
                    update_fields['unit_id'] = None
            
            # 個体数の検証
            if 'abundance' in update_fields:
                try:
                    abundance = int(update_fields['abundance'])
                    if abundance < 0:
                        logger.error("個体数は0以上の整数を指定してください")
                        return False
                    update_fields['abundance'] = abundance
                except (ValueError, TypeError):
                    logger.error("個体数は数値で指定してください")
                    return False
            
            # 更新クエリを構築
            set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
            values = list(update_fields.values())
            values.append(occurrence_id)
            
            query = f"UPDATE occurrences SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cursor.execute(query, values)
            
            self.conn.commit()
            logger.info(f"出現記録を更新しました: ID {occurrence_id}")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"重複する出現記録が既に存在します: {e}")
            self.conn.rollback()
            return False
        except sqlite3.Error as e:
            logger.error(f"出現記録の更新中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    def delete_occurrence(self, occurrence_id: int) -> bool:
        """
        出現記録を削除する
        
        Args:
            occurrence_id (int): 削除する出現記録のID
            
        Returns:
            bool: 削除が成功したかどうか
        """
        try:
            cursor = self.conn.cursor()
            
            # 出現記録の存在確認
            cursor.execute('''
                SELECT o.id, sp.scientific_name, ss.site_name
                FROM occurrences o
                LEFT JOIN species sp ON o.species_id = sp.id
                LEFT JOIN survey_sites ss ON o.site_id = ss.id
                WHERE o.id = ?
            ''', (occurrence_id,))
            
            occurrence = cursor.fetchone()
            if not occurrence:
                logger.error(f"出現記録が見つかりません: ID {occurrence_id}")
                return False
            
            # 削除を実行
            cursor.execute("DELETE FROM occurrences WHERE id = ?", (occurrence_id,))
            
            self.conn.commit()
            logger.info(f"出現記録を削除しました: {occurrence['scientific_name']} (ID: {occurrence_id})")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"出現記録の削除中にエラーが発生しました: {e}")
            self.conn.rollback()
            return False
    
    # ============================================
    # マスターデータ関連のメソッド
    # ============================================
    
    def get_environment_types(self) -> List[Dict[str, Any]]:
        """環境タイプの一覧を取得する"""
        return self._get_master_data('environment_types')
    
    def get_methods(self) -> List[Dict[str, Any]]:
        """調査手法の一覧を取得する"""
        return self._get_master_data('methods')
    
    def get_seasons(self) -> List[Dict[str, Any]]:
        """季節の一覧を取得する"""
        return self._get_master_data('seasons')
    
    def get_units(self) -> List[Dict[str, Any]]:
        """単位の一覧を取得する"""
        return self._get_master_data('units')
    
    def _get_master_data(self, table_name: str) -> List[Dict[str, Any]]:
        """マスターデータを取得する（内部メソッド）"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(f'SELECT * FROM {table_name} ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"{table_name}の取得中にエラーが発生しました: {e}")
            return []
    
    # ============================================
    # データインポート/エクスポート関連のメソッド
    # ============================================
    
    def import_from_csv(self, file_path: str, data_type: str) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        CSVファイルからデータをインポートする
        
        Args:
            file_path (str): インポートするCSVファイルのパス
            data_type (str): データの種類（'species', 'research', 'sites', 'occurrences' のいずれか）
            
        Returns:
            Tuple[int, int, List[Dict[str, Any]]]: (成功件数, 失敗件数, エラーリスト)
        """
        if data_type not in ['species', 'research', 'sites', 'occurrences']:
            logger.error(f"サポートされていないデータタイプです: {data_type}")
            return 0, 0, [{"error": f"サポートされていないデータタイプ: {data_type}"}]
        
        # CSVファイルを読み込む
        data = read_csv_file(file_path)
        if not data:
            return 0, 0, [{"error": "CSVファイルの読み込みに失敗しました"}]
        
        success_count = 0
        error_count = 0
        errors = []
        
        # データタイプに応じた処理を実行
        for i, row in enumerate(data, 1):
            try:
                if data_type == 'species':
                    result = self._import_species(row)
                elif data_type == 'research':
                    result = self._import_research(row)
                elif data_type == 'sites':
                    result = self._import_survey_site(row)
                elif data_type == 'occurrences':
                    result = self._import_occurrence(row)
                
                if result:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append({
                        "row": i,
                        "error": f"{data_type}のインポートに失敗しました",
                        "data": row
                    })
                    
            except Exception as e:
                error_count += 1
                errors.append({
                    "row": i,
                    "error": str(e),
                    "data": row
                })
        
        return success_count, error_count, errors
    
    def _import_species(self, data: Dict[str, Any]) -> bool:
        """生物種データをインポートする（内部メソッド）"""
        # 必須フィールドの検証
        required = ['scientific_name', 'japanese_name']
        is_valid, errors = validate_required_fields(data, required)
        if not is_valid:
            logger.error(f"必須フィールドが不足しています: {', '.join(errors)}")
            return False
        
        # 数値フィールドの変換
        numeric_fields = {
            'body_len_min': parse_float,
            'body_len_max': parse_float,
            'elev_min': parse_int,
            'elev_max': parse_int
        }
        
        kwargs = {}
        for field, parser in numeric_fields.items():
            if field in data and data[field]:
                kwargs[field] = parser(data[field])
        
        # テキストフィールド
        text_fields = ['subfamily', 'dist_text', 'red_list']
        for field in text_fields:
            if field in data and data[field]:
                kwargs[field] = data[field].strip()
        
        # シノニム
        if 'synonyms' in data and data['synonyms']:
            kwargs['synonyms'] = [s.strip() for s in data['synonyms'].split(',') if s.strip()]
        
        # 生物種を追加
        species_id = self.add_species(
            scientific_name=data['scientific_name'].strip(),
            japanese_name=data['japanese_name'].strip(),
            **kwargs
        )
        
        return species_id is not None
    
    def _import_research(self, data: Dict[str, Any]) -> bool:
        """研究論文データをインポートする（内部メソッド）"""
        # 必須フィールドの検証
        required = ['title', 'author', 'year']
        is_valid, errors = validate_required_fields(data, required)
        if not is_valid:
            logger.error(f"必須フィールドが不足しています: {', '.join(errors)}")
            return False
        
        # 年を整数に変換
        try:
            year = int(data['year'])
        except (ValueError, TypeError):
            logger.error(f"無効な年です: {data['year']}")
            return False
        
        # 研究論文を追加
        research_id = self.add_research(
            title=data['title'].strip(),
            author=data['author'].strip(),
            year=year,
            doi=data.get('doi', '').strip() or None,
            content=data.get('content', '').strip() or None
        )
        
        return research_id is not None
    
    def _import_survey_site(self, data: Dict[str, Any]) -> bool:
        """調査地点データをインポートする（内部メソッド）"""
        # 必須フィールドの検証
        required = ['research_id', 'site_name', 'date_start']
        is_valid, errors = validate_required_fields(data, required)
        if not is_valid:
            logger.error(f"必須フィールドが不足しています: {', '.join(errors)}")
            return False
        
        # 研究論文IDを整数に変換
        try:
            research_id = int(data['research_id'])
        except (ValueError, TypeError):
            logger.error(f"無効な研究論文IDです: {data['research_id']}")
            return False
        
        # 日付をパース
        date_start = parse_date(data['date_start'])
        if not date_start:
            logger.error(f"無効な日付形式です: {data['date_start']}")
            return False
        
        # 数値フィールドの変換
        numeric_fields = {
            'environment_type_id': parse_int,
            'season_id': parse_int,
            'latitude': parse_float,
            'longitude': parse_float,
            'elevation': parse_int
        }
        
        kwargs = {}
        for field, parser in numeric_fields.items():
            if field in data and data[field]:
                parsed = parser(data[field])
                if parsed is not None:
                    kwargs[field] = parsed
        
        # 調査地点を追加
        site_id = self.add_survey_site(
            research_id=research_id,
            site_name=data['site_name'].strip(),
            date_start=date_start,
            **kwargs
        )
        
        return site_id is not None
    
    def _import_occurrence(self, data: Dict[str, Any]) -> bool:
        """出現記録データをインポートする（内部メソッド）"""
        # 必須フィールドの検証
        required = ['site_id', 'species_id']
        is_valid, errors = validate_required_fields(data, required)
        if not is_valid:
            logger.error(f"必須フィールドが不足しています: {', '.join(errors)}")
            return False
        
        # 数値フィールドの変換
        numeric_fields = {
            'site_id': int,
            'species_id': int,
            'method_id': parse_int,
            'unit_id': parse_int,
            'abundance': lambda x: int(x) if x else 1
        }
        
        kwargs = {}
        for field, parser in numeric_fields.items():
            if field in data and data[field]:
                try:
                    kwargs[field] = parser(data[field])
                except (ValueError, TypeError) as e:
                    if field in required:
                        raise ValueError(f"無効な{field}です: {data[field]}")
                    # 必須でないフィールドは無視
        
        # 出現記録を追加
        occurrence_id = self.add_occurrence(
            site_id=kwargs['site_id'],
            species_id=kwargs['species_id'],
            method_id=kwargs.get('method_id'),
            unit_id=kwargs.get('unit_id'),
            abundance=kwargs.get('abundance', 1),
            notes=data.get('notes', '').strip() or None
        )
        
        return occurrence_id is not None
    
    def export_to_csv(self, output_dir: str, data_type: str, **filters) -> str:
        """
        データをCSVファイルにエクスポートする
        
        Args:
            output_dir (str): 出力先ディレクトリ
            data_type (str): データの種類（'species', 'research', 'sites', 'occurrences' のいずれか）
            **filters: フィルター条件
            
        Returns:
            str: 出力されたファイルのパス（失敗した場合は空文字列）
        """
        if data_type not in ['species', 'research', 'sites', 'occurrences']:
            logger.error(f"サポートされていないデータタイプです: {data_type}")
            return ""
        
        try:
            # データを取得
            if data_type == 'species':
                data = self.search_species(filters.get('query', ''))
                filename = f"species_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            elif data_type == 'research':
                data = self.search_research(
                    query=filters.get('query'),
                    author=filters.get('author'),
                    year_from=filters.get('year_from'),
                    year_to=filters.get('year_to'),
                    limit=10000  # 大量のデータを取得するため上限を引き上げ
                )
                filename = f"research_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            elif data_type == 'sites':
                data = self.get_survey_sites(
                    research_id=filters.get('research_id'),
                    environment_type_id=filters.get('environment_type_id'),
                    season_id=filters.get('season_id'),
                    limit=10000  # 大量のデータを取得するため上限を引き上げ
                )
                filename = f"sites_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            elif data_type == 'occurrences':
                data = self.get_occurrences(
                    site_id=filters.get('site_id'),
                    species_id=filters.get('species_id'),
                    research_id=filters.get('research_id'),
                    environment_type_id=filters.get('environment_type_id'),
                    season_id=filters.get('season_id'),
                    limit=10000  # 大量のデータを取得するため上限を引き上げ
                )
                filename = f"occurrences_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            if not data:
                logger.warning("エクスポートするデータがありません")
                return ""
            
            # 出力ディレクトリが存在しない場合は作成
            os.makedirs(output_dir, exist_ok=True)
            
            # ファイルパスを生成
            filepath = os.path.join(output_dir, filename)
            
            # CSVに書き出し
            if write_csv_file(filepath, data):
                logger.info(f"{len(data)}件のデータをエクスポートしました: {filepath}")
                return filepath
            else:
                logger.error("CSVファイルの書き込みに失敗しました")
                return ""
                
        except Exception as e:
            logger.error(f"エクスポート中にエラーが発生しました: {e}")
            return ""

# モジュールとしてインポートされた場合のエントリーポイント
if __name__ == "__main__":
    # 使用例
    with AntResearchDB() as db:
        print("データベースが正常に初期化されました。")
        print(f"データベースファイル: {os.path.abspath('database/ant_research.db')}")
        print("\n利用可能なメソッドの例:")
        print("- add_species: 生物種を追加")
        print("- add_research: 研究論文を追加")
        print("- add_survey_site: 調査地点を追加")
        print("- add_occurrence: 出現記録を追加")
        print("- search_species: 生物種を検索")
        print("- search_research: 研究論文を検索")
        print("\n各メソッドの詳細は、help() またはソースコードを参照してください。")
