# アリ類研究データベース

長野県内のアリ類生息情報および先行研究を管理・検索するシステム。特に「同所的に生息する種」の抽出を重視した設計。

## 📋 主要機能

### Phase 1 (MVP - 現バージョン)
- ✅ SQLiteベースのデータベース管理
- ✅ 種マスター・研究・観測記録の統合管理
- ✅ 同所的種の自動抽出
- ✅ 生息環境・標高の統計
- ✅ 研究文献との紐付け
- ✅ CSVインポート/エクスポート
- ✅ PyQt6 GUI (CRUD操作)

### Phase 2 (今後の拡張)
- ⏸️ 全文検索 (FTS5)
- ⏸️ 空間検索 (R-Tree)
- ⏸️ 地図表示 (Folium)
- ⏸️ 統計グラフ (Matplotlib)

---

## 🚀 セットアップ

### 1. 必要な環境

- **Python**: 3.10以上
- **OS**: Windows / macOS / Linux

### 2. パッケージのインストール

```bash
# 仮想環境の作成 (推奨)
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 3. データベースの初期化

```bash
# SQLiteでスキーマを作成
sqlite3 ant_research.db < database_schema.sql

# または Python から実行
python -c "import sqlite3; conn = sqlite3.connect('ant_research.db'); conn.executescript(open('database_schema.sql').read()); conn.close()"
```

### 4. GUIの起動

```bash
python gui_main.py
```

---

## 📂 ファイル構成

```
ant-research-db/
├── README.md                 # このファイル
├── requirements.txt          # 依存パッケージ
├── database_schema.sql       # DDL (テーブル定義)
├── csv_importer.py           # CSVインポートツール
├── query_functions.py        # クエリ関数集
├── gui_main.py               # メインGUI
├── ant_research.db           # SQLiteデータベース (自動生成)
└── csv_data/                 # CSVデータ格納フォルダ
    ├── species.csv           # 種マスター
    ├── research.csv          # 文献情報
    └── records.csv           # 観測記録
```

---

## 📊 CSVフォーマット

### `species.csv` (種マスター)

| 列名 | 型 | 必須 | 例 |
|------|-----|------|-----|
| scientific_name | TEXT | ✅ | Formica japonica |
| japanese_name | TEXT | ✅ | クロヤマアリ |
| subfamily | TEXT | ❌ | Formicinae |
| body_len_mm | REAL | ❌ | 7.5 |
| red_list | TEXT | ❌ | VU |
| synonyms | TEXT | ❌ | クロヤマ, Formica fusca japonica |

### `research.csv` (文献情報)

| 列名 | 型 | 必須 | 例 |
|------|-----|------|-----|
| title | TEXT | ✅ | 長野県のアリ相 |
| author | TEXT | ✅ | 山田太郎 |
| year | INT | ✅ | 2020 |
| doi | TEXT | ❌ | 10.xxxx/xxxxx |
| file_path | TEXT | ❌ | data/pdfs/yamada2020.pdf |

### `records.csv` (観測記録)

| 列名 | 型 | 必須 | 例 |
|------|-----|------|-----|
| research_title | TEXT | ✅ | 長野県のアリ相 |
| site_name | TEXT | ✅ | 松本城周辺 |
| survey_date | TEXT | ❌ | 2020-06-15 |
| latitude | REAL | ❌ | 36.2381 |
| longitude | REAL | ❌ | 137.9691 |
| elevation_m | INT | ❌ | 590 |
| environment | TEXT | ❌ | 市街地 |
| method | TEXT | ❌ | ピットフォールトラップ |
| species_name | TEXT | ✅ | クロヤマアリ |
| abundance | INT | ❌ | 15 |
| unit | TEXT | ❌ | worker |

---

## 🔧 使い方

### CSVデータのインポート

```bash
python csv_importer.py --db ant_research.db --data ./csv_data/
```

**重要:** インポート順序
1. `species.csv` (種を先に登録)
2. `research.csv` (文献情報)
3. `records.csv` (観測記録)

### GUI操作

#### 1. 種の検索
- 上部の検索バーに学名または和名を入力
- リアルタイムでフィルタリング

#### 2. 詳細情報の表示
- 左パネルで種を選択
- 右パネルのタブで以下を確認:
  - **基本情報**: 分類・形態
  - **同所種**: 共起種のリスト
  - **生息環境**: 環境別統計
  - **研究**: 記録文献
  - **詳細記録**: すべての観測データ

#### 3. データの編集
- **追加**: 左下の「➕ 追加」ボタン
- **編集**: 種を選択後「✏️ 編集」ボタン
- **削除**: 種を選択後「🗑️ 削除」ボタン

---

## 🔍 主要クエリ例

### 1. 同所的種の検索

```python
from query_functions import AntDatabaseQuery

db = AntDatabaseQuery('ant_research.db')

# クロヤマアリ (species_id=1) と同所的な種
sympatric_species = db.get_sympatric_species(species_id=1, min_sites=2)
print(sympatric_species)
```

### 2. 環境別の統計

```python
# 生息環境の集計
habitats = db.get_habitats(species_id=1)
print(habitats)
```

### 3. 研究リスト

```python
# 記録された文献
research = db.get_research_list(species_id=1)
print(research)
```

---

## 📝 データ設計のポイント

### 1. 正規化と整合性
- 外部キー制約により参照整合性を保証
- ユニーク制約で重複データを排除

### 2. 名寄せ機能
- `species_synonyms` テーブルで表記揺れを吸収
- NFKC正規化により全角半角を統一

### 3. 同所性の定義
**同一地点の判定基準:**
```
(research_id, site_name, survey_date, latitude, longitude, elevation_m)
```
すべてが一致した場合のみ同一地点とみなす。

### 4. 重複データの扱い
同一地点・同一種・同一手法のデータは **個体数を加算** する。

---

## 🐛 トラブルシューティング

### Q1: `FOREIGN KEY constraint failed`
**原因:** 外部キー制約違反  
**対策:** 参照先データを先に登録（種→研究→記録の順）

### Q2: 種名が見つからない
**原因:** `species_synonyms` に未登録  
**対策:** 
```sql
INSERT INTO species_synonyms (species_id, name, name_normalized, synonym_type)
VALUES (1, '別名', '別名', 'alias');
```

### Q3: GUIが起動しない
**原因:** PyQt6未インストール  
**対策:** 
```bash
pip install PyQt6
```

### Q4: インポートでエラー
- `import_errors.log` を確認
- CSV形式が正しいか確認（UTF-8, カンマ区切り）

---

## 🔐 データのバックアップ

```bash
# データベース全体をコピー
cp ant_research.db ant_research_backup_$(date +%Y%m%d).db

# CSVにエクスポート (GUI から可能)
# または SQL で:
sqlite3 ant_research.db ".mode csv" ".output backup.csv" "SELECT * FROM v_occurrences_readable;"
```

---

## 📚 参考情報

### データベーススキーマ
- `species`: 種マスター
- `species_synonyms`: 名寄せ辞書
- `research`: 文献情報
- `survey_sites`: 調査地点
- `occurrences`: 出現記録 (Fact Table)
- `environment_types`: 環境マスター
- `methods`: 採集方法マスター

### ビュー
- `v_species_full`: 種とシノニムの結合
- `v_occurrences_readable`: 読みやすい出現記録

---

## 📧 サポート

不具合報告・機能要望は Issues へお願いします。

---

## 📄 ライセンス

MIT License (お好みに応じて変更可能)

---

## 🎯 次のステップ

1. ✅ サンプルCSVを作成してインポート
2. ✅ GUIで検索・閲覧
3. ⏩ 実データを少しずつ追加
4. ⏩ Phase 2 機能の検討・実装

---

**Version:** 1.0 (MVP)  
**Last Updated:** 2025-12-10