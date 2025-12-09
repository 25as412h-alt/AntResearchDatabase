# 要件定義書：アリ類研究データベース

| 項目 | 内容 |
| :--- | :--- |
| **System Name** | Ant Research Database |
| **Target** | Python/SQLite Backend Implementation |

## 1\. プロジェクト概要

### 目的

長野県内のアリ類生息情報および先行研究を管理・検索するシステム。特に「同所的に生息する種」の抽出精度を担保するため、データの整合性と正規化を徹底する。

### 主要要件

  * **Strict Consistency:** 外部キー制約、ユニーク制約によるデータ矛盾の物理的排除。
  * **Robust ETL:** CSVインポート時の表記揺れ正規化（名寄せ）と厳密なバリデーション。
  * **Searchability:** 学名/和名の区別なき検索と、FTS5による高速全文検索。

-----

## 2\. 技術スタック

  * **Language:** Python 3.10+
  * **GUI:** PyQt6 / PySide6
  * **Database:** SQLite3
  * **Extensions:**
      * FTS5 (Full-Text Search)
      * R-Tree (Optional for future GIS)
  * **Settings:**
      * `PRAGMA foreign_keys = ON;` (常時必須)

-----

## 3\. データベース設計 (Schema)

### 3.1 ER図 (Mermaid)

```mermaid
erDiagram
    SPECIES ||--o{ SPECIES_SYNONYMS : has_alias
    SPECIES ||--o{ SPECIES_IMAGES : has_image
    SPECIES ||--o{ OCCURRENCES : appears_in
    
    RESEARCH ||--|| RESEARCH_TEXTS : has_content
    RESEARCH ||--o{ SURVEY_SITES : conducted_at
    
    ENVIRONMENT_TYPES ||--o{ SURVEY_SITES : classifies
    SEASONS ||--o{ SURVEY_SITES : temporal_context
    
    SURVEY_SITES ||--o{ OCCURRENCES : contains
    METHODS ||--o{ OCCURRENCES : collected_by
    UNITS ||--o{ OCCURRENCES : counted_in

    SPECIES {
        int id PK
        string scientific_name UK
        string japanese_name
        float body_len_min
        float body_len_max
        string dist_text
        string red_list
    }
    
    SPECIES_SYNONYMS {
        int id PK
        int species_id FK
        string name UK "検索用"
        string name_normalized UK "正規化・名寄せ用"
    }

    RESEARCH {
        int id PK
        string doi UK
        string title
        string author
        int year
        string unique_hash UK "MD5(title+year+author)"
    }

    RESEARCH_TEXTS {
        int research_id FK
        string content "FTS Index"
    }

    SURVEY_SITES {
        int id PK
        int research_id FK
        string site_name
        string date_start
        int environment_type_id FK
        float latitude
        float longitude
        int elevation
        constraint UK "research+site+date+loc"
    }

    OCCURRENCES {
        int id PK
        int site_id FK
        int species_id FK
        int method_id FK
        int unit_id FK
        int abundance
        constraint UK "site+species+method+unit"
    }
```

### 3.2 テーブル定義詳細 (DDL要件)

#### A. マスター・辞書 (Dictionaries)

*表記揺れを排除するため、定型項目はすべてID管理とする。*

**`species` (生物種マスター)**

  * `id`: INTEGER PK
  * `scientific_name`: TEXT UNIQUE NOT NULL
  * `japanese_name`: TEXT NOT NULL
  * Others: `subfamily`, `body_len_min`, `body_len_max`, `dist_text`, `elev_min`, `elev_max`, `red_list`

**`species_synonyms` (名寄せ辞書)**
*目的: 和名、学名、旧名、別名をすべてここに格納し、入力揺れを吸収する。*

  * `id`: INTEGER PK
  * `species_id`: INTEGER FK -\> `species.id` (**ON DELETE CASCADE**)
  * `name`: TEXT NOT NULL (表示用)
  * `name_normalized`: TEXT UNIQUE NOT NULL (検索・マッチング用。全角半角・スペース正規化済み)
  * `type`: TEXT ('scientific', 'japanese', 'synonym')

**`environment_types`, `methods`, `seasons`, `units`**

  * 各テーブルに `id` (PK) と `name` (UNIQUE) を持つ。
  * `units`例: 'worker', 'colony', 'queen' など。

#### B. 研究データ (Research Data)

**`research` (文献メタデータ)**

  * `id`: INTEGER PK
  * `doi`: TEXT UNIQUE (NULL許容)
  * `title`: TEXT NOT NULL
  * `author`: TEXT NOT NULL
  * `year`: INTEGER NOT NULL
  * `unique_hash`: TEXT UNIQUE NOT NULL (DOIがない場合の重複排除キー。`md5(title + year + author)`)

**`research_texts` (全文検索)**

  * **Engine:** FTS5
  * **Columns:** `research_id` (UNINDEXED), `content`
  * **Tokenizer:** `unicode61 (remove_diacritics=1, tokenchars="-_. ")`
  * *Note: スニペット生成のため contentless オプションは使用しない。*

#### C. 観測データ (Field Records)

**`survey_sites` (調査地点)**
*目的: 「いつ・どこで」を一意に特定する。*

  * `id`: INTEGER PK
  * `research_id`: INTEGER FK -\> `research.id` (**ON DELETE CASCADE**)
  * `site_name`: TEXT NOT NULL
  * `date_start`: TEXT (ISO8601: YYYY-MM-DD)
  * `environment_type_id`: INTEGER FK
  * `season_id`: INTEGER FK
  * `latitude`: REAL (Check: -90\~90)
  * `longitude`: REAL (Check: -180\~180)
  * `elevation`: INTEGER (Check: \> -500)
  * **UNIQUE Constraint:** `(research_id, site_name, date_start, latitude, longitude, elevation)`
      * *Note: 厳密な同一地点定義。わずかでもズレれば別地点として扱う。*

**`occurrences` (出現記録)**
*目的: 「何が・どうやって・どれくらい」いたか。*

  * `id`: INTEGER PK
  * `site_id`: INTEGER FK -\> `survey_sites.id` (**ON DELETE CASCADE**)
  * `species_id`: INTEGER FK -\> `species.id` (**ON DELETE RESTRICT**)
  * `method_id`: INTEGER FK
  * `unit_id`: INTEGER FK (個体数単位)
  * `abundance`: INTEGER (0以上の整数)
  * **UNIQUE Constraint:** `(site_id, species_id, method_id, unit_id)`
      * *Note: 同一地点・同一種でも、採集法や単位が異なれば別レコード。*

-----

## 4\. データインポート (ETL) 要件

### 4.1 全体方針

1.  **Idempotency (冪等性):** スクリプトは何度実行しても安全であること。
2.  **Log:** エラー行は `error_log.csv` に出力し、プロセスを停止させない（スキップ処理）。
3.  **Normalization:** 全ての入力文字列に対し、`unicodedata.normalize('NFKC', text)` を適用してからDB照合を行う。

### 4.2 CSVファイル定義

以下の4ファイルを所定フォルダから読み込む。

  * `00_dicts.csv`: 環境・手法・季節・単位の初期マスタ。
  * `01_species.csv`: 種情報。synonyms列はカンマ区切りで複数指定。
  * `02_research.csv`: 論文情報。txt\_file列がある場合はファイル読み込み。
  * `03_records.csv`: 観測データ（非正規化テーブル）。
      * **Columns:** `doi_or_title`, `site_name`, `date`, `lat`, `lon`, `elev`, `env`, `method`, `species_name`, `count`, `unit`

### 4.3 ロジック仕様

**1. 種名の解決**

  * `species_name` (CSV) を正規化し、`species_synonyms.name_normalized` を検索。
  * ヒットしなければエラーログに出力し、その行をスキップ（自動登録はしない）。

**2. 地点の特定**

  * `(research_id, site_name, date, lat, lon, elev)` で `survey_sites` を検索。
  * 存在しなければ新規作成、存在すればその `id` を使用。

**3. 重複データの扱い (occurrences)**

  * ユニーク制約 `(site_id, species_id, method_id, unit_id)` に抵触する場合：
  * **Action:** 既存レコードの `abundance` に今回の値を **加算 (ADD)** する。

-----

## 5\. インデックス設計 (Performance)

初期化時に以下のインデックスを作成すること。

  * `IDX_species_sci ON species(scientific_name)`
  * `IDX_synonyms_norm ON species_synonyms(name_normalized)` (ETL高速化の要)
  * `IDX_sites_loc ON survey_sites(latitude, longitude, elevation)` (空間検索用)
  * `IDX_occurrences_lookup ON occurrences(species_id, site_id)` (共起種検索用)

-----

## 6\. 今後の拡張性 (Future Roadmap)

  * **Spatial Search:** R-Tree モジュールの導入による高速な範囲検索。
  * **Uncertainty:** 座標精度 (`uncertainty_m`) を利用したファジー検索。
  * **Analysis:** 季節性 (`season_id`) や環境選好性 (`environment_type_id`) の統計出力。

-----

### 次のステップ

この要件定義に基づき、以下の作業を行う準備ができています。ご希望のものを指示してください。

1.  SQLite用の完全な **SQL作成スクリプト（DDL）** の生成。
2.  データインポート用 **Python ETLスクリプト（Pandas/SQLite3使用）** のプロトタイプ作成。
3.  **SQLAlchemy** または **Pydantic** を用いたデータモデルの定義コード作成。
