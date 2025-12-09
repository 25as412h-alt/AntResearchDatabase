#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
import csv
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

class ARDBApp:
    # ユーザー視点の日本語関数名を用いた実装
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ARDB - Ant Research Database")

        # データベース出力先フォルダ
        self.db_dir = os.path.join(os.path.dirname(__file__), "db_output")
        self.ディレクトリを作成する()
        self.db_path = os.path.join(self.db_dir, "ardb.sqlite")
        self.conn = None
        self.データベースを作成する()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.csv_tab = ttk.Frame(self.notebook)
        self.list_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.csv_tab, text="CSV入力")
        self.notebook.add(self.list_tab, text="一覧")

        # タブの構築
        self._CSV入力タブを作成する()
        self._一覧タブを作成する()
        self.レコードをツリーに読み込む()

        self.root.protocol("WM_DELETE_WINDOW", self.ウィンドウを閉じる)

    # ディレクトリ作成
    def ディレクトリを作成する(self):
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

    # データベース作成
    def データベースを作成する(self):
        self.conn = sqlite3.connect(self.db_path)
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                header TEXT,
                row_data TEXT,
                inserted_at TEXT
            )
        ''')
        self.conn.commit()

    # CSV入力タブの構築
    def _CSV入力タブを作成する(self):
        frame = self.csv_tab
        self.csv_path_var = tk.StringVar()

        lbl = ttk.Label(frame, text="CSVファイルを選択してください:")
        lbl.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        path_entry = ttk.Entry(frame, textvariable=self.csv_path_var, width=60)
        path_entry.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        browse_btn = ttk.Button(frame, text="参照", command=self._CSV選択)
        browse_btn.grid(row=1, column=1, padx=5, pady=5)

        load_btn = ttk.Button(frame, text="読み込む", command=self._CSVを_dbへ格納する)
        load_btn.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.csv_status = ttk.Label(frame, text="")
        self.csv_status.grid(row=2, column=1, padx=5, pady=5, sticky="w")

    # CSV選択ダイアログ
    def _CSV選択(self):
        file_path = filedialog.askopenfilename(title="CSVファイルを選択",
                                               filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if file_path:
            self.csv_path_var.set(file_path)

    # CSVをデータベースへ格納
    def _CSVを_dbへ格納する(self):
        path = self.csv_path_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showerror("エラー", "有効なCSVファイルを指定してください。")
            return
        try:
            self._CSVを_dbへ格納する処理(path)
            self.csv_status.config(text=f"読み込み完了: {os.path.basename(path)}")
            self.レコードをツリーに読み込む()
        except Exception as e:
            messagebox.showerror("エラー", f"CSVの読み込みに失敗しました: {e}")

    # 実際のCSV格納処理
    def _CSVを_dbへ格納する処理(self, csv_path: str):
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if not headers:
                raise ValueError("CSVにヘッダがありません")
            header_json = json.dumps(headers, ensure_ascii=False)
            file_name = os.path.basename(csv_path)
            cur = self.conn.cursor()
            for row in reader:
                row_json = json.dumps(row, ensure_ascii=False)
                cur.execute('''
                    INSERT INTO records (file_name, header, row_data, inserted_at)
                    VALUES (?, ?, ?, ?)
                ''', (file_name, header_json, row_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.conn.commit()

    # 一覧タブの構築
    def _一覧タブを作成する(self):
        frame = self.list_tab
        self.tree = ttk.Treeview(frame, columns=("id","file_name","header","inserted_at"), show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("file_name", text="ファイル名")
        self.tree.heading("header", text="ヘッダ(JSON)")
        self.tree.heading("inserted_at", text="挿入時刻")
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("file_name", width=180)
        self.tree.column("header", width=260)
        self.tree.column("inserted_at", width=140)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 詳細表示エリア
        detail_frame = ttk.Frame(frame)
        detail_frame.pack(side="right", fill="both", expand=True)
        detail_label = ttk.Label(detail_frame, text="詳細データ")
        detail_label.pack(anchor="nw")
        self.detail_text = tk.Text(detail_frame, height=15, wrap="none")
        self.detail_text.pack(fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._レコード選択時処理)

    # レコード選択時の処理
    def _レコード選択時処理(self, event):
        items = self.tree.selection()
        if not items:
            return
        item_id = self.tree.item(items[0])["values"][0]
        cur = self.conn.cursor()
        cur.execute("SELECT row_data FROM records WHERE id=?", (item_id,))
        row = cur.fetchone()
        if not row:
            return
        row_json = row[0]
        try:
            data = json.loads(row_json)
        except Exception:
            data = {}
        self.detail_text.delete("1.0", tk.END)
        if isinstance(data, dict):
            for k, v in data.items():
                self.detail_text.insert(tk.END, f"{k}: {v}\n")
        else:
            self.detail_text.insert(tk.END, str(data))

    # レコードをツリーに読み込む
    def レコードをツリーに読み込む(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        cur = self.conn.cursor()
        cur.execute("SELECT id, file_name, header, inserted_at FROM records ORDER BY inserted_at DESC")
        for row in cur.fetchall():
            self.tree.insert("", "end", values=row)

    # ウィンドウを閉じる
    def ウィンドウを閉じる(self):
        if self.conn:
            self.conn.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ARDBApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()


