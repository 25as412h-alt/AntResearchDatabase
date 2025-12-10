#!/usr/bin/env python3
"""
アリ類研究データベース メインGUI
PyQt6ベースの管理・検索システム
"""

import sys
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QTabWidget, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QPushButton, QMessageBox, QDialog, QFormLayout,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMenuBar, QMenu, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
import pandas as pd

from query_functions import AntDatabaseQuery


class SpeciesDialog(QDialog):
    """種の追加・編集ダイアログ"""
    def __init__(self, parent=None, species_data=None):
        super().__init__(parent)
        self.species_data = species_data
        self.setWindowTitle("種情報の編集" if species_data else "新規種の追加")
        self.setMinimumWidth(500)
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        
        # 入力フィールド
        self.scientific_name = QLineEdit()
        self.japanese_name = QLineEdit()
        self.subfamily = QLineEdit()
        self.body_len_mm = QDoubleSpinBox()
        self.body_len_mm.setRange(0, 50)
        self.body_len_mm.setDecimals(1)
        self.body_len_mm.setSuffix(" mm")
        
        self.red_list = QComboBox()
        self.red_list.addItems(['', 'EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD'])
        
        self.synonyms = QTextEdit()
        self.synonyms.setMaximumHeight(80)
        self.synonyms.setPlaceholderText("別名をカンマ区切りで入力 (例: クロヤマ, Formica fusca japonica)")
        
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(100)
        
        # 既存データの読み込み
        if self.species_data:
            self.scientific_name.setText(self.species_data.get('scientific_name', ''))
            self.japanese_name.setText(self.species_data.get('japanese_name', ''))
            self.subfamily.setText(self.species_data.get('subfamily', ''))
            if self.species_data.get('body_len_mm'):
                self.body_len_mm.setValue(float(self.species_data['body_len_mm']))
            self.red_list.setCurrentText(self.species_data.get('red_list', ''))
            self.notes.setPlainText(self.species_data.get('notes', ''))
        
        # レイアウト
        layout.addRow("学名 *:", self.scientific_name)
        layout.addRow("和名 *:", self.japanese_name)
        layout.addRow("亜科:", self.subfamily)
        layout.addRow("体長:", self.body_len_mm)
        layout.addRow("レッドリスト:", self.red_list)
        layout.addRow("別名・シノニム:", self.synonyms)
        layout.addRow("備考:", self.notes)
        
        # ボタン
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("キャンセル")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
    
    def get_data(self):
        """入力データを辞書で返す"""
        return {
            'scientific_name': self.scientific_name.text().strip(),
            'japanese_name': self.japanese_name.text().strip(),
            'subfamily': self.subfamily.text().strip(),
            'body_len_mm': self.body_len_mm.value() if self.body_len_mm.value() > 0 else None,
            'red_list': self.red_list.currentText(),
            'synonyms': self.synonyms.toPlainText().strip(),
            'notes': self.notes.toPlainText().strip()
        }


class MainWindow(QMainWindow):
    def __init__(self, db_path='ant_research.db'):
        super().__init__()
        self.db_path = db_path
        self.db_query = AntDatabaseQuery(db_path)
        self.current_species_id = None
        
        self.setWindowTitle("アリ類研究データベース")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()
        self.load_species_list()
        self.update_status()
    
    def init_ui(self):
        # メニューバー
        self.create_menu()
        
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 検索バー
        search_layout = QHBoxLayout()
        search_label = QLabel("種名検索:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("学名または和名を入力...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)
        
        # スプリッター (左右分割)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左パネル: 種リスト
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.species_list = QListWidget()
        self.species_list.itemClicked.connect(self.on_species_selected)
        left_layout.addWidget(QLabel("種リスト:"))
        left_layout.addWidget(self.species_list)
        
        # CRUD ボタン
        button_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 追加")
        edit_btn = QPushButton("✏️ 編集")
        delete_btn = QPushButton("🗑️ 削除")
        add_btn.clicked.connect(self.add_species)
        edit_btn.clicked.connect(self.edit_species)
        delete_btn.clicked.connect(self.delete_species)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        left_layout.addLayout(button_layout)
        
        splitter.addWidget(left_panel)
        
        # 右パネル: 詳細タブ
        self.detail_tabs = QTabWidget()
        self.detail_tabs.addTab(self.create_info_tab(), "📋 基本情報")
        self.detail_tabs.addTab(self.create_sympatric_tab(), "🐜 同所種")
        self.detail_tabs.addTab(self.create_habitat_tab(), "🌲 生息環境")
        self.detail_tabs.addTab(self.create_research_tab(), "📚 研究")
        self.detail_tabs.addTab(self.create_records_tab(), "📍 詳細記録")
        
        splitter.addWidget(self.detail_tabs)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)

        # 新規CSV Editorパネル: Add / List / Edit の3トップタブ + species/research/recordsのサブタブ
        self.csv_editor_panel = self.create_csv_editor_panel()
        main_layout.addWidget(self.csv_editor_panel)
        
        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
    
    def create_menu(self):
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル")
        
        import_action = QAction("CSVインポート...", self)
        import_action.triggered.connect(self.import_csv)
        file_menu.addAction(import_action)
        
        export_action = QAction("エクスポート...", self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("終了", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ")
        about_action = QAction("バージョン情報", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_info_tab(self):
        """基本情報タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        font = QFont("Monospace", 10)
        self.info_text.setFont(font)
        
        layout.addWidget(self.info_text)
        return widget
    
    def create_sympatric_tab(self):
        """同所種タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.sympatric_table = QTableWidget()
        self.sympatric_table.setColumnCount(4)
        self.sympatric_table.setHorizontalHeaderLabels(
            ["学名", "和名", "共起地点数", "地点名"]
        )
        self.sympatric_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(QLabel("この種と同じ場所で記録された種:"))
        layout.addWidget(self.sympatric_table)
        
        return widget
    
    def create_habitat_tab(self):
        """生息環境タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.habitat_table = QTableWidget()
        self.habitat_table.setColumnCount(6)
        self.habitat_table.setHorizontalHeaderLabels(
            ["環境タイプ", "地点数", "総個体数", "平均個体数", "標高範囲(m)", "地点名"]
        )
        self.habitat_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(QLabel("環境別の出現統計:"))
        layout.addWidget(self.habitat_table)
        
        return widget
    
    def create_research_tab(self):
        """研究タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.research_table = QTableWidget()
        self.research_table.setColumnCount(5)
        self.research_table.setHorizontalHeaderLabels(
            ["タイトル", "著者", "年", "地点数", "記録数"]
        )
        self.research_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(QLabel("この種を記録した研究:"))
        layout.addWidget(self.research_table)
        
        return widget
    
    def create_records_tab(self):
        """詳細記録タブ"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(9)
        self.records_table.setHorizontalHeaderLabels(
            ["研究", "年", "地点名", "調査日", "緯度", "経度", "標高", "環境", "個体数"]
        )
        self.records_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(QLabel("すべての出現記録:"))
        layout.addWidget(self.records_table)
        
        return widget
    
    def load_species_list(self, filter_text=''):
        """種リストの読み込み"""
        self.species_list.clear()
        
        if filter_text:
            results = self.db_query.search_species(filter_text)
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT id, scientific_name, japanese_name 
                FROM species 
                ORDER BY japanese_name
            """)
            results = [{'id': r[0], 'scientific_name': r[1], 'japanese_name': r[2]} 
                      for r in cursor.fetchall()]
            conn.close()
        
        for species in results:
            display_text = f"{species['japanese_name']} ({species['scientific_name']})"
            item = self.species_list.addItem(display_text)
            # IDを保存
            self.species_list.item(self.species_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, species['id']
            )
    
    def on_search_changed(self):
        """検索テキスト変更時"""
        # デバウンス処理 (300ms後に実行)
        if hasattr(self, 'search_timer'):
            self.search_timer.stop()
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: self.load_species_list(self.search_input.text())
        )
        self.search_timer.start(300)
    
    def on_species_selected(self, item):
        """種が選択された時"""
        self.current_species_id = item.data(Qt.ItemDataRole.UserRole)
        self.load_species_details()
    
    def load_species_details(self):
        """選択種の詳細情報を読み込み"""
        if not self.current_species_id:
            return
        
        # 基本情報
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT * FROM v_species_full WHERE id = ?",
            (self.current_species_id,)
        )
        species = cursor.fetchone()
        conn.close()
        
        if species:
            info_html = f"""
            <h2>{species[2]} <i>({species[1]})</i></h2>
            <table border="1" cellpadding="5">
            <tr><th>項目</th><th>値</th></tr>
            <tr><td>ID</td><td>{species[0]}</td></tr>
            <tr><td>学名</td><td><i>{species[1]}</i></td></tr>
            <tr><td>和名</td><td>{species[2]}</td></tr>
            <tr><td>亜科</td><td>{species[3] or '-'}</td></tr>
            <tr><td>別名・シノニム</td><td>{species[4] or '-'}</td></tr>
            </table>
            """
            self.info_text.setHtml(info_html)
        
        # 同所種
        self.load_sympatric_species()
        
        # 生息環境
        self.load_habitats()
        
        # 研究リスト
        self.load_research_list()
        
        # 詳細記録
        self.load_occurrence_records()
    
    def load_sympatric_species(self):
        """同所種を読み込み"""
        df = self.db_query.get_sympatric_species(self.current_species_id)
        self.populate_table(self.sympatric_table, df)
    
    def load_habitats(self):
        """生息環境を読み込み"""
        df = self.db_query.get_habitats(self.current_species_id)
        
        # 標高範囲を整形
        if not df.empty and 'min_elevation' in df.columns:
            df['elevation_range'] = df.apply(
                lambda r: f"{int(r['min_elevation']) if pd.notna(r['min_elevation']) else '-'} ~ "
                         f"{int(r['max_elevation']) if pd.notna(r['max_elevation']) else '-'}",
                axis=1
            )
            df = df[['environment', 'site_count', 'total_individuals', 
                    'avg_abundance', 'elevation_range', 'sites']]
        
        self.populate_table(self.habitat_table, df)
    
    def load_research_list(self):
        """研究リストを読み込み"""
        df = self.db_query.get_research_list(self.current_species_id)
        self.populate_table(self.research_table, df[['title', 'author', 'year', 
                                                      'sites_count', 'total_records']])
    
    def load_occurrence_records(self):
        """詳細記録を読み込み"""
        df = self.db_query.get_occurrence_details(self.current_species_id)
        
        # 単位付き個体数
        if not df.empty:
            df['abundance_unit'] = df['abundance'].astype(str) + ' ' + df['unit']
            df = df[['research', 'year', 'site_name', 'survey_date', 
                    'latitude', 'longitude', 'elevation_m', 'environment', 'abundance_unit']]
        
        self.populate_table(self.records_table, df)
    
    def populate_table(self, table, df):
        """DataFrameをTableWidgetに表示"""
        table.setRowCount(0)
        
        if df.empty:
            return
        
        table.setRowCount(len(df))
        
        for i, row in df.iterrows():
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value) if pd.notna(value) else '')
                table.setItem(i, j, item)
    
    def add_species(self):
        """種の追加"""
        dialog = SpeciesDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            if not data['scientific_name'] or not data['japanese_name']:
                QMessageBox.warning(self, "入力エラー", "学名と和名は必須です。")
                return
            
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("PRAGMA foreign_keys = ON")
                
                # 種を登録
                cursor = conn.execute("""
                    INSERT INTO species 
                    (scientific_name, japanese_name, subfamily, body_len_mm, red_list, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data['scientific_name'], data['japanese_name'], 
                      data['subfamily'], data['body_len_mm'], 
                      data['red_list'], data['notes']))
                
                species_id = cursor.lastrowid
                
                # シノニムを登録
                for name in [data['scientific_name'], data['japanese_name']]:
                    conn.execute("""
                        INSERT OR IGNORE INTO species_synonyms 
                        (species_id, name, name_normalized, synonym_type)
                        VALUES (?, ?, ?, 'primary')
                    """, (species_id, name, name))
                
                # 追加シノニム
                if data['synonyms']:
                    for syn in data['synonyms'].split(','):
                        syn = syn.strip()
                        if syn:
                            conn.execute("""
                                INSERT OR IGNORE INTO species_synonyms 
                                (species_id, name, name_normalized, synonym_type)
                                VALUES (?, ?, ?, 'alias')
                            """, (species_id, syn, syn))
                
                conn.commit()
                conn.close()
                
                self.load_species_list()
                self.update_status()
                QMessageBox.information(self, "成功", "種を追加しました。")
                
            except sqlite3.IntegrityError as e:
                QMessageBox.critical(self, "エラー", f"登録エラー: {e}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"予期しないエラー: {e}")
    
    def edit_species(self):
        """種の編集"""
        if not self.current_species_id:
            QMessageBox.warning(self, "警告", "種を選択してください。")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM species WHERE id = ?", (self.current_species_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return
        
        species_data = {
            'scientific_name': row[1],
            'japanese_name': row[2],
            'subfamily': row[3],
            'body_len_mm': row[4],
            'red_list': row[5],
            'notes': row[6]
        }
        
        dialog = SpeciesDialog(self, species_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("""
                    UPDATE species 
                    SET scientific_name = ?, japanese_name = ?, subfamily = ?,
                        body_len_mm = ?, red_list = ?, notes = ?
                    WHERE id = ?
                """, (data['scientific_name'], data['japanese_name'], 
                      data['subfamily'], data['body_len_mm'], 
                      data['red_list'], data['notes'], self.current_species_id))
                
                conn.commit()
                conn.close()
                
                self.load_species_list()
                self.load_species_details()
                QMessageBox.information(self, "成功", "更新しました。")
                
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"更新エラー: {e}")
    
    def delete_species(self):
        """種の削除"""
        if not self.current_species_id:
            QMessageBox.warning(self, "警告", "種を選択してください。")
            return
        
        reply = QMessageBox.question(
            self, "確認", 
            "本当に削除しますか?\n(関連する出現記録も削除されます)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("DELETE FROM species WHERE id = ?", (self.current_species_id,))
                conn.commit()
                conn.close()
                
                self.current_species_id = None
                self.load_species_list()
                self.update_status()
                QMessageBox.information(self, "成功", "削除しました。")
                
            except sqlite3.IntegrityError:
                QMessageBox.critical(
                    self, "エラー", 
                    "この種には出現記録が存在するため削除できません。"
                )
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"削除エラー: {e}")
    
    def import_csv(self):
        """CSVインポート"""
        directory = QFileDialog.getExistingDirectory(self, "CSVフォルダを選択")
        if directory:
            QMessageBox.information(
                self, "インポート", 
                f"コマンドラインで以下を実行してください:\n\n"
                f"python csv_importer.py --db {self.db_path} --data {directory}"
            )
    
    def export_data(self):
        """データエクスポート"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "エクスポート先を選択", "", "CSV Files (*.csv)"
        )
        if file_path:
            # 将来的にはここから各 CSV へ追記されたデータを DB に取り込むワークフローを追加
            try:
                df = pd.read_sql_query(
                    "SELECT * FROM v_occurrences_readable", 
                    sqlite3.connect(self.db_path)
                )
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "成功", f"エクスポートしました:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"エクスポートエラー: {e}")
    
    def show_about(self):
        """バージョン情報"""
        stats = self.db_query.statistics_summary()
        QMessageBox.about(
            self, "バージョン情報",
            f"<h2>アリ類研究データベース</h2>"
            f"<p>Version 1.0 (MVP)</p>"
            f"<p><b>データベース統計:</b></p>"
            f"<ul>"
            f"<li>登録種数: {stats['total_species']}</li>"
            f"<li>研究数: {stats['total_research']}</li>"
            f"<li>調査地点数: {stats['total_sites']}</li>"
            f"<li>出現記録数: {stats['total_occurrences']}</li>"
            f"<li>最新研究年: {stats['latest_research_year']}</li>"
            f"</ul>"
        )
    
    def update_status(self):
        """ステータスバー更新"""
        stats = self.db_query.statistics_summary()
        self.status_bar.showMessage(
            f"種: {stats['total_species']} | "
            f"研究: {stats['total_research']} | "
            f"地点: {stats['total_sites']} | "
            f"記録: {stats['total_occurrences']}"
        )
    
    def closeEvent(self, event):
        """ウィンドウクローズ時"""
        self.db_query.close()
        event.accept()

    def append_species_to_csv(self):
        """species.csv へデータを追記"""
        from csv_csv_writer import append_row_to_csv
        from pathlib import Path
        row = {
            'scientific_name': self.species_add_sci.text().strip(),
            'japanese_name': self.species_add_jp.text().strip(),
            'subfamily': self.species_add_sub.text().strip(),
            'body_len_mm': self.species_add_len.value() if self.species_add_len.value() > 0 else "",
            'red_list': self.species_add_red.currentText(),
            'synonyms': self.species_add_synonyms.text().strip(),
            'notes': self.species_add_notes.toPlainText().strip(),
        }
        if not row['scientific_name'] or not row['japanese_name']:
            QMessageBox.warning(self, "入力エラー", "学名と和名は必須です。")
            return
        csv_path = Path("csv") / "species.csv"
        append_row_to_csv(csv_path, row)
        QMessageBox.information(self, "成功", "species.csv へ追記しました。")
        # クリア
        self.species_add_sci.clear()
        self.species_add_jp.clear()
        self.species_add_sub.clear()
        self.species_add_len.setValue(0)
        self.species_add_red.setCurrentIndex(0)
        self.species_add_synonyms.clear()
        self.species_add_notes.clear()

    def append_research_to_csv(self):
        """research.csv へデータを追記"""
        from csv_csv_writer import append_row_to_csv
        from pathlib import Path
        row = {
            'title': self.research_add_title.text().strip(),
            'author': self.research_add_author.text().strip(),
            'year': self.research_add_year.text().strip(),
            'doi': self.research_add_doi.text().strip(),
            'file_path': self.research_add_file_path.text().strip(),
        }
        if not row['title'] or not row['author'] or not row['year']:
            QMessageBox.warning(self, "入力エラー", "タイトル・著者・年は必須です。")
            return
        csv_path = Path("csv") / "research.csv"
        append_row_to_csv(csv_path, row)
        QMessageBox.information(self, "成功", "research.csv へ追記しました。")
        self.research_add_title.clear()
        self.research_add_author.clear()
        self.research_add_year.clear()
        self.research_add_doi.clear()
        self.research_add_file_path.clear()

    def append_records_to_csv(self):
        """records.csv へデータを追記"""
        from csv_csv_writer import append_row_to_csv
        from pathlib import Path
        row = {
            'research_title': self.records_add_research_title.text().strip(),
            'site_name': self.records_add_site.text().strip(),
            'survey_date': self.records_add_date.text().strip(),
            'latitude': self.records_add_lat.text().strip(),
            'longitude': self.records_add_lon.text().strip(),
            'elevation_m': self.records_add_elev.text().strip(),
            'environment': self.records_add_env.text().strip(),
            'method': self.records_add_method.text().strip(),
            'species_name': self.records_add_species.text().strip(),
            'abundance': self.records_add_abundance.text().strip(),
            'unit': self.records_add_unit.text().strip(),
        }
        # いくつか必須項目のチェック（シンプルな検証のみ）
        if not row['research_title'] or not row['site_name']:
            QMessageBox.warning(self, "入力エラー", "研究タイトルと地点名は必須です。")
            return
        csv_path = Path("csv") / "records.csv"
        append_row_to_csv(csv_path, row)
        QMessageBox.information(self, "成功", "records.csv へ追記しました。")
        self.records_add_research_title.clear()
        self.records_add_site.clear()
        self.records_add_date.clear()
        self.records_add_lat.clear()
        self.records_add_lon.clear()
        self.records_add_elev.clear()
        self.records_add_env.clear()
        self.records_add_method.clear()
        self.records_add_species.clear()
        self.records_add_abundance.clear()
        self.records_add_unit.clear()
    def create_csv_editor_panel(self):
        """CSV 追加/一覧/編集削除を統合したエディタパネル"""
        panel = QTabWidget()

        # 追加タブ
        add_tab = QTabWidget()
        # species 追加フォーム
        species_add_widget = QWidget()
        species_add_layout = QFormLayout(species_add_widget)
        self.species_add_sci = QLineEdit()
        self.species_add_jp = QLineEdit()
        self.species_add_sub = QLineEdit()
        self.species_add_len = QDoubleSpinBox()
        self.species_add_len.setRange(0, 50)
        self.species_add_len.setDecimals(1)
        self.species_add_len.setSuffix(" mm")
        self.species_add_red = QComboBox()
        self.species_add_red.addItems(['', 'EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD'])
        self.species_add_synonyms = QLineEdit()
        self.species_add_notes = QTextEdit()
        self.species_add_notes.setMaximumHeight(80)
        add_btn = QPushButton("追加CSVへ追記")
        add_btn.clicked.connect(self.append_species_to_csv)
        species_add_layout.addRow("学名 *:", self.species_add_sci)
        species_add_layout.addRow("和名 *:", self.species_add_jp)
        species_add_layout.addRow("亜科:", self.species_add_sub)
        species_add_layout.addRow("体長:", self.species_add_len)
        species_add_layout.addRow("レッドリスト:", self.species_add_red)
        species_add_layout.addRow("別名・シノニム:", self.species_add_synonyms)
        species_add_layout.addRow("備考:", self.species_add_notes)
        species_add_layout.addRow(add_btn)
        add_tab.addTab(species_add_widget, "species.csv 追加")
        # research 追加フォーム
        research_add_widget = QWidget()
        research_add_layout = QFormLayout(research_add_widget)
        self.research_add_title = QLineEdit()
        self.research_add_author = QLineEdit()
        self.research_add_year = QLineEdit()
        self.research_add_doi = QLineEdit()
        self.research_add_file_path = QLineEdit()
        self.research_add_btn = QPushButton("追加CSVへ追記")
        self.research_add_btn.clicked.connect(self.append_research_to_csv)
        research_add_layout.addRow("タイトル:", self.research_add_title)
        research_add_layout.addRow("著者:", self.research_add_author)
        research_add_layout.addRow("年:", self.research_add_year)
        research_add_layout.addRow("DOI:", self.research_add_doi)
        research_add_layout.addRow("ファイルパス:", self.research_add_file_path)
        research_add_layout.addRow(self.research_add_btn)
        add_tab.addTab(research_add_widget, "research.csv 追加")
        # records 追加フォーム
        records_add_widget = QWidget()
        records_add_layout = QFormLayout(records_add_widget)
        self.records_add_research_title = QLineEdit()
        self.records_add_site = QLineEdit()
        self.records_add_date = QLineEdit()
        self.records_add_lat = QLineEdit()
        self.records_add_lon = QLineEdit()
        self.records_add_elev = QLineEdit()
        self.records_add_env = QLineEdit()
        self.records_add_method = QLineEdit()
        self.records_add_species = QLineEdit()
        self.records_add_abundance = QLineEdit()
        self.records_add_unit = QLineEdit()
        self.records_add_btn = QPushButton("追加CSVへ追記")
        self.records_add_btn.clicked.connect(self.append_records_to_csv)
        records_add_layout.addRow("研究タイトル:", self.records_add_research_title)
        records_add_layout.addRow("地点名:", self.records_add_site)
        records_add_layout.addRow("調査日(YYYY-MM-DD):", self.records_add_date)
        records_add_layout.addRow("緯度:", self.records_add_lat)
        records_add_layout.addRow("経度:", self.records_add_lon)
        records_add_layout.addRow("標高(m):", self.records_add_elev)
        records_add_layout.addRow("環境:", self.records_add_env)
        records_add_layout.addRow("方法:", self.records_add_method)
        records_add_layout.addRow("種名:", self.records_add_species)
        records_add_layout.addRow("個体数:", self.records_add_abundance)
        records_add_layout.addRow("単位:", self.records_add_unit)
        records_add_layout.addRow(self.records_add_btn)
        add_tab.addTab(records_add_widget, "records.csv 追加")
        panel.addTab(add_tab, "追加")

        # 一覧タブ
        list_tab = QTabWidget()
        list_tab.addTab(QWidget(), "species.csv 一覧")
        list_tab.addTab(QWidget(), "research.csv 一覧")
        list_tab.addTab(QWidget(), "records.csv 一覧")
        panel.addTab(list_tab, "一覧")

        # 編集削除タブ
        edit_tab = QTabWidget()
        edit_tab.addTab(QWidget(), "species.csv 編集/削除")
        edit_tab.addTab(QWidget(), "research.csv 編集/削除")
        edit_tab.addTab(QWidget(), "records.csv 編集/削除")
        panel.addTab(edit_tab, "編集削除")

        return panel


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # モダンなスタイル
    
    # データベースファイルの確認
    db_path = 'ant_research.db'
    if not Path(db_path).exists():
        reply = QMessageBox.question(
            None, "データベース未作成",
            f"{db_path} が見つかりません。\n新規作成しますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 空のデータベースを作成
            conn = sqlite3.connect(db_path)
            conn.close()
            QMessageBox.information(
                None, "初期化",
                "database_schema.sql を実行してデータベースを初期化してください。"
            )
        else:
            sys.exit(0)
    
    window = MainWindow(db_path)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
