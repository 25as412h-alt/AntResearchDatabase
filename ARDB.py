# ARDB.py
# Ant Research Database - SQLite 初期化ユーティリティ
# Python 3.10+
from __future__ import annotations
import sqlite3
import unicodedata
import re
from pathlib import Path
from typing import Optional


DEFAULT_PRAGMAS = (
    "PRAGMA foreign_keys = ON;",
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
)


def normalize_text(text: Optional[str]) -> Optional[str]:
    """NFKC 正規化、全角半角・空白正規化、小文字化。Noneはそのまま返す。"""
    if text is None:
        return None
    s = unicodedata.normalize("NFKC", text)
    s = s.strip()
    # 全角スペースを半角にし、複数空白を1つに
    s = re.sub(r"\s+", " ", s.replace("\u3000", " "))
    return s.lower()


class ARDB:
    """SQLite データベースのスキーマ初期化と基本操作を提供する軽量ユーティリティ。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas()

    def _apply_pragmas(self) -> None:
        cur = self.conn.cursor()
        for p in DEFAULT_PRAGMAS:
            cur.execute(p)
        cur.close()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def initialize_schema(self) -> None:
        """仕様に基づいたテーブル・インデックスを作成する。冪等性あり。"""
        cur = self.conn.cursor()

        # マスター・辞書テーブル
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS species (
                id INTEGER PRIMARY KEY,
                scientific_name TEXT UNIQUE NOT NULL,
                japanese_name TEXT NOT NULL,
                subfamily TEXT,
                body_len_min REAL,
                body_len_max REAL,
                dist_text TEXT,
                elev_min INTEGER,
                elev_max INTEGER,
                red_list TEXT
            );

            CREATE TABLE IF NOT EXISTS species_synonyms (
                id INTEGER PRIMARY KEY,
                species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                name_normalized TEXT UNIQUE NOT NULL,
                type TEXT
            );

            CREATE TABLE IF NOT EXISTS environment_types (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY,
                doi TEXT UNIQUE,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                year INTEGER NOT NULL,
                unique_hash TEXT UNIQUE NOT NULL
            );

            -- survey_sites: 一意制約を厳密に設定
            CREATE TABLE IF NOT EXISTS survey_sites (
                id INTEGER PRIMARY KEY,
                research_id INTEGER NOT NULL REFERENCES research(id) ON DELETE CASCADE,
                site_name TEXT NOT NULL,
                date_start TEXT,
                environment_type_id INTEGER REFERENCES environment_types(id),
                season_id INTEGER REFERENCES seasons(id),
                latitude REAL CHECK(latitude >= -90 AND latitude <= 90),
                longitude REAL CHECK(longitude >= -180 AND longitude <= 180),
                elevation INTEGER CHECK(elevation > -500),
                UNIQUE (research_id, site_name, date_start, latitude, longitude, elevation)
            );

            CREATE TABLE IF NOT EXISTS occurrences (
                id INTEGER PRIMARY KEY,
                site_id INTEGER NOT NULL REFERENCES survey_sites(id) ON DELETE CASCADE,
                species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE RESTRICT,
                method_id INTEGER REFERENCES methods(id),
                unit_id INTEGER REFERENCES units(id),
                abundance INTEGER NOT NULL CHECK (abundance >= 0),
                UNIQUE (site_id, species_id, method_id, unit_id)
            );
            """
        )

        # FTS5 仮想テーブルの作成（存在チェックをして作成）
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
            ("research_texts",),
        )
        if not cur.fetchone():
            try:
                cur.execute(
                    "CREATE VIRTUAL TABLE research_texts USING fts5(research_id UNINDEXED, content, tokenize='unicode61 remove_diacritics=1 tokenchars=\"-_. \"');"
                )
            except sqlite3.OperationalError:
                # FTS5 が利用できない場合は例外を投げる
                raise RuntimeError("FTS5 がこの SQLite ビルドで利用できません。")

        # インデックス
        cur.executescript(
            """
            CREATE INDEX IF NOT EXISTS IDX_species_sci ON species(scientific_name);
            CREATE INDEX IF NOT EXISTS IDX_synonyms_norm ON species_synonyms(name_normalized);
            CREATE INDEX IF NOT EXISTS IDX_sites_loc ON survey_sites(latitude, longitude, elevation);
            CREATE INDEX IF NOT EXISTS IDX_occurrences_lookup ON occurrences(species_id, site_id);
            """
        )

        self.conn.commit()
        cur.close()

    def insert_or_get_lookup(self, table: str, name: str) -> int:
        """単純な辞書テーブル用。name が存在すれば id を返し、なければ挿入する。"""
        name = normalize_text(name)
        if not name:
            raise ValueError("name は空にできません。")
        cur = self.conn.cursor()
        cur.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            cur.close()
            return int(row["id"])
        cur.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,))
        self.conn.commit()
        last = cur.lastrowid
        cur.close()
        return int(last)

    def add_species(self, scientific_name: str, japanese_name: str, **kwargs) -> int:
        """species を新規挿入。既存 scientific_name があればその id を返す。"""
        sci = normalize_text(scientific_name)
        jap = normalize_text(japanese_name) or ""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM species WHERE scientific_name = ?", (sci,))
        row = cur.fetchone()
        if row:
            cur.close()
            return int(row["id"])
        cols = ["scientific_name", "japanese_name"]
        vals = [sci, jap]
        for k in ("subfamily", "body_len_min", "body_len_max", "dist_text", "elev_min", "elev_max", "red_list"):
            if k in kwargs and kwargs[k] is not None:
                cols.append(k)
                vals.append(kwargs[k])
        placeholders = ",".join("?" for _ in vals)
        cur.execute(f"INSERT INTO species({','.join(cols)}) VALUES ({placeholders})", vals)
        self.conn.commit()
        last = cur.lastrowid
        cur.close()
        return int(last)

    def add_synonym(self, species_id: int, name: str, typ: str = "synonym") -> int:
        """species_synonyms に登録。name_normalized は自動生成。"""
        nm = normalize_text(name)
        if not nm:
            raise ValueError("name は空にできません。")
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM species_synonyms WHERE name_normalized = ?", (nm,))
        row = cur.fetchone()
        if row:
            cur.close()
            return int(row["id"])
        cur.execute(
            "INSERT INTO species_synonyms (species_id, name, name_normalized, type) VALUES (?, ?, ?, ?)",
            (species_id, name, nm, typ),
        )
        self.conn.commit()
        last = cur.lastrowid
        cur.close()
        return int(last)


if __name__ == "__main__":
    # 実行時はカレントディレクトリに ardb.sqlite3 を作成して初期化する簡易ユーティリティ
    db_file = Path.cwd() / "ardb.sqlite3"
    db = ARDB(db_file)
    try:
        db.initialize_schema()
        print(f"Initialized database at {db_file}")
    finally:
        db.close()