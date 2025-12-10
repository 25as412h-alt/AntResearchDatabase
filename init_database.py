#!/usr/bin/env python3
"""
データベース初期化スクリプト (エラー表示付き)
使用法: python init_database.py
"""

import sqlite3
import sys
from pathlib import Path


def init_database(db_path='ant_research.db', sql_file='database_schema.sql'):
    """
    SQLファイルを実行してデータベースを初期化
    エラーが発生した場合は詳細を表示
    """
    print("=" * 60)
    print("アリ類研究データベース 初期化ツール")
    print("=" * 60)
    
    # SQLファイルの存在確認
    sql_path = Path(sql_file)
    if not sql_path.exists():
        print(f"❌ エラー: SQLファイルが見つかりません")
        print(f"   パス: {sql_path.absolute()}")
        print(f"\n📁 現在のディレクトリ: {Path.cwd()}")
        return False
    
    print(f"✓ SQLファイル確認: {sql_path.absolute()}")
    
    # SQLファイルを読み込み
    try:
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        print(f"✓ SQLファイル読み込み成功 ({len(sql_script)} 文字)")
    except Exception as e:
        print(f"❌ SQLファイル読み込みエラー: {e}")
        return False
    
    # データベース接続
    db_path_obj = Path(db_path)
    print(f"\n📦 データベースパス: {db_path_obj.absolute()}")
    
    # 既存DBの確認
    if db_path_obj.exists():
        response = input(f"\n⚠️  {db_path} は既に存在します。上書きしますか? (y/N): ")
        if response.lower() != 'y':
            print("キャンセルしました。")
            return False
        db_path_obj.unlink()
        print("✓ 既存データベースを削除しました")
    
    try:
        # データベース作成
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        print("✓ データベース接続成功")
        
        # SQLスクリプトを実行
        print("\n🔧 SQLスクリプトを実行中...")
        cursor = conn.cursor()
        
        # スクリプトを個別に実行してエラー箇所を特定
        statements = sql_script.split(';')
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue
            
            try:
                cursor.execute(statement)
                success_count += 1
                # テーブル作成などの重要な処理は表示
                if 'CREATE TABLE' in statement.upper():
                    table_name = statement.split('CREATE TABLE')[1].split('(')[0].strip()
                    print(f"  ✓ テーブル作成: {table_name}")
                elif 'CREATE INDEX' in statement.upper():
                    index_name = statement.split('CREATE INDEX')[1].split('ON')[0].strip()
                    print(f"  ✓ インデックス作成: {index_name}")
                elif 'CREATE VIEW' in statement.upper():
                    view_name = statement.split('CREATE VIEW')[1].split('AS')[0].strip()
                    print(f"  ✓ ビュー作成: {view_name}")
                elif 'INSERT INTO' in statement.upper():
                    table_name = statement.split('INSERT INTO')[1].split('(')[0].strip()
                    if 'environment_types' in table_name or 'methods' in table_name:
                        print(f"  ✓ 初期データ挿入: {table_name}")
            except sqlite3.Error as e:
                error_count += 1
                print(f"\n❌ SQL実行エラー (文 {i}):")
                print(f"   エラー: {e}")
                print(f"   SQL: {statement[:200]}...")
                
                # 致命的エラーの場合は停止
                if 'syntax error' in str(e).lower():
                    print("\n⚠️  構文エラーが発生しました。SQLファイルを確認してください。")
                    conn.close()
                    return False
        
        conn.commit()
        print(f"\n✅ SQLスクリプト実行完了!")
        print(f"   成功: {success_count} 文")
        if error_count > 0:
            print(f"   エラー: {error_count} 文")
        
        # テーブル一覧を表示
        print("\n📋 作成されたテーブル:")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = cursor.fetchall()
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   • {table[0]} ({count} レコード)")
        
        # インデックス一覧
        print("\n🔍 作成されたインデックス:")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        indexes = cursor.fetchall()
        for idx in indexes:
            print(f"   • {idx[0]}")
        
        # ビュー一覧
        print("\n👁️  作成されたビュー:")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='view'
            ORDER BY name
        """)
        views = cursor.fetchall()
        for view in views:
            print(f"   • {view[0]}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ データベース初期化が完了しました!")
        print(f"📁 場所: {db_path_obj.absolute()}")
        print("=" * 60)
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ データベースエラー: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_database(db_path='ant_research.db'):
    """データベースの健全性チェック"""
    print("\n🔍 データベースの検証中...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 外部キー制約が有効か確認
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        if fk_status == 1:
            print("✓ 外部キー制約: 有効")
        else:
            print("⚠️  外部キー制約: 無効 (警告)")
        
        # 各テーブルの整合性チェック
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()[0]
        if result == 'ok':
            print("✓ データベース整合性: OK")
        else:
            print(f"❌ 整合性エラー: {result}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 検証エラー: {e}")
        return False


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='アリ類研究データベース 初期化ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python init_database.py
  python init_database.py --db my_ants.db
  python init_database.py --sql schema.sql
        """
    )
    parser.add_argument('--db', default='ant_research.db', 
                       help='データベースファイル名 (デフォルト: ant_research.db)')
    parser.add_argument('--sql', default='database_schema.sql',
                       help='SQLファイル名 (デフォルト: database_schema.sql)')
    parser.add_argument('--verify', action='store_true',
                       help='初期化後に検証を実行')
    
    args = parser.parse_args()
    
    # 初期化実行
    success = init_database(args.db, args.sql)
    
    if success:
        # 検証
        if args.verify:
            verify_database(args.db)
        
        print("\n📖 次のステップ:")
        print("1. CSVファイルを準備")
        print("   • species.csv")
        print("   • research.csv")
        print("   • records.csv")
        print()
        print("2. データをインポート:")
        print(f"   python csv_importer.py --db {args.db} --data ./csv_data")
        print()
        print("3. GUIを起動:")
        print(f"   python gui_main.py")
        
        return 0
    else:
        print("\n❌ 初期化に失敗しました")
        return 1


if __name__ == '__main__':
    sys.exit(main())
