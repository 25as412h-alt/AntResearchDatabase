-- アリ類研究データベース DDL (MVP版)
-- SQLite 3.35+

-- ==================== マスターテーブル ====================

-- 種マスター
CREATE TABLE species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    japanese_name TEXT NOT NULL,
    subfamily TEXT,
    body_len_mm REAL CHECK(body_len_mm > 0),
    red_list TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 種名辞書 (表記揺れ吸収)
CREATE TABLE species_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id INTEGER NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name_normalized TEXT NOT NULL UNIQUE,
    synonym_type TEXT DEFAULT 'alias',
    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE
);

-- 環境タイプマスター
CREATE TABLE environment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT
);

-- 採集方法マスター
CREATE TABLE methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT
);

-- ==================== 研究データ ====================

-- 文献情報
CREATE TABLE research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    year INTEGER NOT NULL CHECK(year >= 1900 AND year <= 2100),
    doi TEXT UNIQUE,
    file_path TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(title, year, author)
);

-- 調査地点
CREATE TABLE survey_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id INTEGER NOT NULL,
    site_name TEXT NOT NULL,
    survey_date TEXT,
    env_type_id INTEGER,
    latitude REAL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL CHECK(longitude BETWEEN -180 AND 180),
    elevation_m INTEGER CHECK(elevation_m > -500),
    notes TEXT,
    FOREIGN KEY (research_id) REFERENCES research(id) ON DELETE CASCADE,
    FOREIGN KEY (env_type_id) REFERENCES environment_types(id),
    UNIQUE(research_id, site_name, survey_date, latitude, longitude)
);

-- 出現記録 (Fact Table)
CREATE TABLE occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    species_id INTEGER NOT NULL,
    method_id INTEGER,
    abundance INTEGER DEFAULT 0 CHECK(abundance >= 0),
    unit TEXT DEFAULT 'worker',
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES survey_sites(id) ON DELETE CASCADE,
    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE RESTRICT,
    FOREIGN KEY (method_id) REFERENCES methods(id),
    UNIQUE(site_id, species_id, method_id, unit)
);

-- ==================== インデックス ====================

CREATE INDEX idx_species_sci ON species(scientific_name);
CREATE INDEX idx_species_jpn ON species(japanese_name);
CREATE INDEX idx_synonyms_norm ON species_synonyms(name_normalized);
CREATE INDEX idx_sites_location ON survey_sites(latitude, longitude, elevation_m);
CREATE INDEX idx_sites_research ON survey_sites(research_id);
CREATE INDEX idx_occurrences_species ON occurrences(species_id);
CREATE INDEX idx_occurrences_site ON occurrences(site_id);
CREATE INDEX idx_occurrences_lookup ON occurrences(species_id, site_id);

-- ==================== トリガー ====================

CREATE TRIGGER update_species_timestamp 
AFTER UPDATE ON species
FOR EACH ROW
BEGIN
    UPDATE species SET updated_at = datetime('now', 'localtime') WHERE id = NEW.id;
END;

-- ==================== 初期データ ====================

INSERT INTO environment_types (name, description) VALUES
    ('森林', '自然林・人工林'),
    ('草地', '草原・牧草地'),
    ('市街地', '都市部・住宅地'),
    ('農地', '水田・畑地'),
    ('河川敷', '河川・湖沼周辺'),
    ('その他', '未分類');

INSERT INTO methods (name, description) VALUES
    ('ピットフォールトラップ', '落とし穴式トラップ'),
    ('ベイトトラップ', '餌によるおびき寄せ'),
    ('ハンドコレクション', '手採り'),
    ('スウィーピング', '捕虫網での掬い取り'),
    ('ツルグレン装置', '土壌サンプルからの抽出'),
    ('その他', '記載なし・不明');

-- ==================== ビュー ====================

CREATE VIEW v_species_full AS
SELECT 
    s.id,
    s.scientific_name,
    s.japanese_name,
    s.subfamily,
    GROUP_CONCAT(DISTINCT sy.name, '; ') AS synonyms
FROM species s
LEFT JOIN species_synonyms sy ON s.id = sy.species_id
GROUP BY s.id;

CREATE VIEW v_occurrences_readable AS
SELECT 
    o.id,
    r.title AS research_title,
    r.year AS research_year,
    ss.site_name,
    ss.survey_date,
    et.name AS environment,
    s.scientific_name,
    s.japanese_name,
    o.abundance,
    o.unit,
    m.name AS method
FROM occurrences o
JOIN survey_sites ss ON o.site_id = ss.id
JOIN species s ON o.species_id = s.id
JOIN research r ON ss.research_id = r.id
LEFT JOIN environment_types et ON ss.env_type_id = et.id
LEFT JOIN methods m ON o.method_id = m.id
ORDER BY r.year DESC, ss.survey_date DESC;