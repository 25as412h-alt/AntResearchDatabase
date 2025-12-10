# セットアップガイド - 詳細版

## 📁 ファイル配置

### 推奨フォルダ構成

```
E:\Ant\Ant Research Database\
├── ant_research.db              (自動生成)
├── database_schema.sql          (配置済み)
├── init_database.py             (新規作成)
├── csv_importer.py              (配置済み)
├── query_functions.py           (配置済み)
├── gui_main.py                  (配置済み)
├── requirements.txt             (配置済み)
├── csv/                         (あなたのCSVフォルダ)
│   ├── species.csv
│   ├── research.csv
│   └── records.csv
└── logs/                        (エラーログ用、自動生成)
    └── import_errors.log
```

### CSVファイルの配置

**現在の場所:**
```
E:\Ant\Ant Research Database\csv\
```

**このままでOKです！** インポート時にこのパスを指定します。

---

## 🚀 実行手順

### ステップ1: データベース初期化

```bash
# コマンドプロンプトまたはPowerShellを開く
cd "E:\Ant\Ant Research Database"

# データベースを初期化 (エラー表示付き)
python init_database.py
```

**出力例:**
```
============================================================
アリ類研究データベース 初期化ツール
============================================================
✓ SQLファイル確認: E:\Ant\Ant Research Database\database_schema.sql
✓ SQLファイル読み込み成功 (12345 文字)

📦 データベースパス: E:\Ant\Ant Research Database\ant_research.db

🔧 SQLスクリプトを実行中...
  ✓ テーブル作成: species
  ✓ テーブル作成: species_synonyms
  ...
✅ SQLスクリプト実行完了!
```

**エラーが出た場合:**
- エラーメッセージをコピーして確認
- どの行で失敗したかが表示されます

---

### ステップ2: CSVインポート

```bash
# 同じフォルダで実行
python csv_importer.py --db ant_research.db --data "E:\Ant\Ant Research Database\csv"

# または相対パスで
python csv_importer.py --db ant_research.db --data ./csv
```

**インポートの流れ:**
```
Importing species from E:\Ant\Ant Research Database\csv\species.csv
✓ Formica japonica (クロヤマアリ)
✓ Camponotus japonicus (クロオオアリ)
...

Importing research from E:\Ant\Ant Research Database\csv\research.csv
✓ 長野県のアリ相 (2020)
...

Importing records from E:\Ant\Ant Research Database\csv\records.csv
✓ クロヤマアリ at 松本城周辺
...

✅ Import completed!
```

**エラーログの確認:**
```bash
# エラーがあった場合、ログファイルが生成されます
type import_errors.log   # Windows
cat import_errors.log    # macOS/Linux
```

---

### ステップ3: GUI起動

```bash
python gui_main.py
```

---

## 🔧 トラブルシューティング

### Q1: `python` コマンドが認識されない

**原因:** Pythonがパスに登録されていない

**対策:**
```bash
# Pythonのフルパスを確認
where python   # Windows
which python   # macOS/Linux

# フルパスで実行
C:\Users\YourName\AppData\Local\Programs\Python\Python310\python.exe init_database.py
```

または環境変数PATHに追加：
1. 「システムの詳細設定」を開く
2. 「環境変数」をクリック
3. `Path` に Python のインストールフォルダを追加

---

### Q2: `ModuleNotFoundError: No module named 'PyQt6'`

**原因:** 必要なパッケージがインストールされていない

**対策:**
```bash
# 依存パッケージを一括インストール
pip install -r requirements.txt

# または個別にインストール
pip install PyQt6 pandas
```

---

### Q3: CSV読み込みエラー `FileNotFoundError`

**原因:** CSVファイルが見つからない

**確認方法:**
```bash
# ファイルの存在確認 (Windows)
dir "E:\Ant\Ant Research Database\csv"

# 出力例
species.csv
research.csv
records.csv
```

**対策:**
- パスが正しいか確認
- ファイル名が正確か確認（拡張子も含む）
- 引用符でパスを囲む（スペースが含まれる場合）

---

### Q4: SQLエラー `UNIQUE constraint failed`

**原因:** 重複データが存在する

**対策1: データベースを再初期化**
```bash
# 既存DBを削除して再作成
python init_database.py
```

**対策2: 重複行を削除**
- CSVファイルを開いて重複行を削除
- 学名 (scientific_name) は一意である必要があります

---

### Q5: 文字化け

**原因:** CSVファイルの文字コードが UTF-8 ではない

**対策:**
1. CSVファイルをテキストエディタで開く
2. 「名前を付けて保存」
3. エンコーディングを **UTF-8** に指定して保存

**推奨エディタ:**
- Visual Studio Code
- Notepad++
- サクラエディタ

---

## 📊 サンプルCSVの作成

まだCSVファイルがない場合、以下のサンプルを使用できます：

### `species.csv`

```csv
scientific_name,japanese_name,subfamily,body_len_mm,red_list,synonyms
Formica japonica,クロヤマアリ,Formicinae,7.5,,クロヤマ
Camponotus japonicus,クロオオアリ,Formicinae,12.0,,クロオオ
Lasius japonicus,トビイロケアリ,Formicinae,4.5,,トビイロ
```

### `research.csv`

```csv
title,author,year,doi,file_path
長野県のアリ相,山田太郎,2020,,
松本市のアリ類調査,田中花子,2021,,
```

### `records.csv`

```csv
research_title,site_name,survey_date,latitude,longitude,elevation_m,environment,method,species_name,abundance,unit
長野県のアリ相,松本城周辺,2020-06-15,36.2381,137.9691,590,市街地,ピットフォールトラップ,クロヤマアリ,15,worker
長野県のアリ相,松本城周辺,2020-06-15,36.2381,137.9691,590,市街地,ピットフォールトラップ,クロオオアリ,8,worker
松本市のアリ類調査,美ヶ原高原,2021-07-10,36.2000,138.1000,2000,草地,ハンドコレクション,トビイロケアリ,25,worker
```

**保存方法:**
1. 各内容をテキストエディタにコピー
2. UTF-8で保存
3. `E:\Ant\Ant Research Database\csv\` に配置

---

## 🎯 ワンライナーで全実行

すべてを一度に実行する場合：

```bash
# PowerShell
cd "E:\Ant\Ant Research Database"
python init_database.py && python csv_importer.py --db ant_research.db --data ./csv && python gui_main.py
```

```bash
# コマンドプロンプト
cd "E:\Ant\Ant Research Database"
python init_database.py & python csv_importer.py --db ant_research.db --data ./csv & python gui_main.py
```

---

## ✅ 動作確認チェックリスト

### 初期化完了後
- [ ] `ant_research.db` ファイルが作成された
- [ ] テーブルが10個以上作成された
- [ ] 初期データ（環境・手法）が挿入された

### インポート完了後
- [ ] エラーログが0件
- [ ] species テーブルにデータが入った
- [ ] occurrences テーブルに記録が入った

### GUI起動後
- [ ] ウィンドウが開いた
- [ ] 種リストが表示された
- [ ] 検索が動作する
- [ ] 詳細タブが切り替わる

---

## 📞 サポート

問題が解決しない場合、以下の情報を添えて質問してください：

1. **実行したコマンド**
2. **エラーメッセージ全文**
3. **Python バージョン** (`python --version`)
4. **OS** (Windows 10/11, macOS, Linux)
5. **ファイル配置** (`dir` や `ls` の出力)

---

**次は実際に実行してみてください！** 🚀
