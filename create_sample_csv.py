#!/usr/bin/env python3
"""
サンプルCSVファイル作成スクリプト
使用法: python create_sample_csv.py
"""

import csv
from pathlib import Path


def create_sample_csvs(output_dir='csv'):
    """サンプルCSVファイルを作成"""
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("サンプルCSVファイル作成ツール")
    print("=" * 60)
    
    # 1. species.csv
    species_file = output_path / 'species.csv'
    print(f"\n📝 作成中: {species_file}")
    
    species_data = [
        {
            'scientific_name': 'Formica japonica',
            'japanese_name': 'クロヤマアリ',
            'subfamily': 'Formicinae',
            'body_len_mm': '7.5',
            'red_list': '',
            'synonyms': 'クロヤマ,Formica fusca japonica'
        },
        {
            'scientific_name': 'Camponotus japonicus',
            'japanese_name': 'クロオオアリ',
            'subfamily': 'Formicinae',
            'body_len_mm': '12.0',
            'red_list': '',
            'synonyms': 'クロオオ'
        },
        {
            'scientific_name': 'Lasius japonicus',
            'japanese_name': 'トビイロケアリ',
            'subfamily': 'Formicinae',
            'body_len_mm': '4.5',
            'red_list': '',
            'synonyms': 'トビイロ'
        },
        {
            'scientific_name': 'Myrmica kotokui',
            'japanese_name': 'アシナガアリ',
            'subfamily': 'Myrmicinae',
            'body_len_mm': '5.0',
            'red_list': '',
            'synonyms': 'アシナガ'
        },
        {
            'scientific_name': 'Pristomyrmex pungens',
            'japanese_name': 'アミメアリ',
            'subfamily': 'Myrmicinae',
            'body_len_mm': '3.5',
            'red_list': '',
            'synonyms': 'アミメ'
        }
    ]
    
    with open(species_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=species_data[0].keys())
        writer.writeheader()
        writer.writerows(species_data)
    
    print(f"  ✓ {len(species_data)} 種を作成")
    
    # 2. research.csv
    research_file = output_path / 'research.csv'
    print(f"\n📝 作成中: {research_file}")
    
    research_data = [
        {
            'title': '長野県のアリ相',
            'author': '山田太郎',
            'year': '2020',
            'doi': '',
            'file_path': ''
        },
        {
            'title': '松本市のアリ類調査',
            'author': '田中花子',
            'year': '2021',
            'doi': '',
            'file_path': ''
        },
        {
            'title': '上高地におけるアリ類の垂直分布',
            'author': '佐藤次郎',
            'year': '2022',
            'doi': '',
            'file_path': ''
        }
    ]
    
    with open(research_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=research_data[0].keys())
        writer.writeheader()
        writer.writerows(research_data)
    
    print(f"  ✓ {len(research_data)} 件の研究を作成")
    
    # 3. records.csv
    records_file = output_path / 'records.csv'
    print(f"\n📝 作成中: {records_file}")
    
    records_data = [
        # 松本城周辺 (市街地)
        {
            'research_title': '長野県のアリ相',
            'site_name': '松本城周辺',
            'survey_date': '2020-06-15',
            'latitude': '36.2381',
            'longitude': '137.9691',
            'elevation_m': '590',
            'environment': '市街地',
            'method': 'ピットフォールトラップ',
            'species_name': 'クロヤマアリ',
            'abundance': '15',
            'unit': 'worker'
        },
        {
            'research_title': '長野県のアリ相',
            'site_name': '松本城周辺',
            'survey_date': '2020-06-15',
            'latitude': '36.2381',
            'longitude': '137.9691',
            'elevation_m': '590',
            'environment': '市街地',
            'method': 'ピットフォールトラップ',
            'species_name': 'クロオオアリ',
            'abundance': '8',
            'unit': 'worker'
        },
        {
            'research_title': '長野県のアリ相',
            'site_name': '松本城周辺',
            'survey_date': '2020-06-15',
            'latitude': '36.2381',
            'longitude': '137.9691',
            'elevation_m': '590',
            'environment': '市街地',
            'method': 'ピットフォールトラップ',
            'species_name': 'トビイロケアリ',
            'abundance': '22',
            'unit': 'worker'
        },
        # 美ヶ原高原 (草地)
        {
            'research_title': '松本市のアリ類調査',
            'site_name': '美ヶ原高原',
            'survey_date': '2021-07-10',
            'latitude': '36.2000',
            'longitude': '138.1000',
            'elevation_m': '2000',
            'environment': '草地',
            'method': 'ハンドコレクション',
            'species_name': 'トビイロケアリ',
            'abundance': '25',
            'unit': 'worker'
        },
        {
            'research_title': '松本市のアリ類調査',
            'site_name': '美ヶ原高原',
            'survey_date': '2021-07-10',
            'latitude': '36.2000',
            'longitude': '138.1000',
            'elevation_m': '2000',
            'environment': '草地',
            'method': 'ハンドコレクション',
            'species_name': 'アシナガアリ',
            'abundance': '12',
            'unit': 'worker'
        },
        # 上高地 (森林)
        {
            'research_title': '上高地におけるアリ類の垂直分布',
            'site_name': '上高地河童橋付近',
            'survey_date': '2022-08-05',
            'latitude': '36.2509',
            'longitude': '137.6358',
            'elevation_m': '1500',
            'environment': '森林',
            'method': 'ピットフォールトラップ',
            'species_name': 'クロヤマアリ',
            'abundance': '30',
            'unit': 'worker'
        },
        {
            'research_title': '上高地におけるアリ類の垂直分布',
            'site_name': '上高地河童橋付近',
            'survey_date': '2022-08-05',
            'latitude': '36.2509',
            'longitude': '137.6358',
            'elevation_m': '1500',
            'environment': '森林',
            'method': 'ピットフォールトラップ',
            'species_name': 'アミメアリ',
            'abundance': '18',
            'unit': 'worker'
        },
        {
            'research_title': '上高地におけるアリ類の垂直分布',
            'site_name': '上高地河童橋付近',
            'survey_date': '2022-08-05',
            'latitude': '36.2509',
            'longitude': '137.6358',
            'elevation_m': '1500',
            'environment': '森林',
            'method': 'ベイトトラップ',
            'species_name': 'クロオオアリ',
            'abundance': '5',
            'unit': 'worker'
        }
    ]
    
    with open(records_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=records_data[0].keys())
        writer.writeheader()
        writer.writerows(records_data)
    
    print(f"  ✓ {len(records_data)} 件の記録を作成")
    
    print("\n" + "=" * 60)
    print("✅ サンプルCSVファイルの作成が完了しました！")
    print(f"📁 保存先: {output_path.absolute()}")
    print("=" * 60)
    
    print("\n📊 作成されたファイル:")
    print(f"  • {species_file.name} ({len(species_data)} 行)")
    print(f"  • {research_file.name} ({len(research_data)} 行)")
    print(f"  • {records_file.name} ({len(records_data)} 行)")
    
    print("\n📖 次のステップ:")
    print("1. データベースを初期化:")
    print("   python init_database.py")
    print()
    print("2. CSVをインポート:")
    print(f"   python csv_importer.py --db ant_research.db --data {output_dir}")
    print()
    print("3. GUIを起動:")
    print("   python gui_main.py")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='サンプルCSVファイルを作成')
    parser.add_argument('--output', default='csv', 
                       help='出力ディレクトリ (デフォルト: csv)')
    parser.add_argument('--force', action='store_true',
                       help='既存ファイルを上書き')
    
    args = parser.parse_args()
    
    output_path = Path(args.output)
    
    # 既存ファイルチェック
    if output_path.exists() and not args.force:
        existing_files = list(output_path.glob('*.csv'))
        if existing_files:
            print(f"⚠️  {output_path} に既にCSVファイルが存在します:")
            for f in existing_files:
                print(f"  • {f.name}")
            
            response = input("\n上書きしますか? (y/N): ")
            if response.lower() != 'y':
                print("キャンセルしました。")
                return
    
    create_sample_csvs(args.output)


if __name__ == '__main__':
    main()
