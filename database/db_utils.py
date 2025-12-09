"""
データベース操作を補助するユーティリティ関数群
"""
import csv
import os
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
from datetime import datetime
import unicodedata
import hashlib

# ロギング設定
logger = logging.getLogger('ARDB.utils')

def normalize_text(text: str) -> str:
    """
    テキストを正規化する（全角・半角、大文字・小文字の統一など）
    
    Args:
        text (str): 正規化するテキスト
        
    Returns:
        str: 正規化されたテキスト
    """
    if not text:
        return ""
    # NFKC正規化（全角英数字→半角、全角スペース→半角スペースなど）
    normalized = unicodedata.normalize('NFKC', str(text).strip())
    # 連続する空白を1つに置換
    normalized = ' '.join(normalized.split())
    return normalized

def generate_unique_hash(title: str, author: str, year: int) -> str:
    """
    研究論文の一意のハッシュを生成する
    
    Args:
        title (str): 論文タイトル
        author (str): 著者名
        year (int): 出版年
        
    Returns:
        str: 生成されたハッシュ値
    """
    hash_input = f"{title}{author}{year}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

def parse_date(date_str: str) -> Optional[str]:
    """
    日付文字列をISO形式（YYYY-MM-DD）にパースする
    
    Args:
        date_str (str): パースする日付文字列
        
    Returns:
        Optional[str]: ISO形式の日付文字列（パースできない場合はNone）
    """
    if not date_str:
        return None
    
    # 一般的な日付形式をサポート
    date_formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',  # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
        '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',  # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
        '%Y',  # 年のみ
        '%Y-%m', '%Y/%m',  # 年月のみ
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # 年のみの場合は1月1日として扱う
            if fmt == '%Y':
                return dt.strftime('%Y-01-01')
            # 年月のみの場合は1日として扱う
            elif fmt in ('%Y-%m', '%Y/%m'):
                return dt.strftime('%Y-%m-01')
            # 完全な日付の場合はそのまま返す
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    logger.warning(f"日付形式が認識できません: {date_str}")
    return None

def read_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """
    CSVファイルを読み込んで辞書のリストとして返す
    
    Args:
        file_path (str): CSVファイルのパス
        
    Returns:
        List[Dict[str, Any]]: CSVの各行を辞書に変換したリスト
    """
    if not os.path.exists(file_path):
        logger.error(f"ファイルが見つかりません: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return [row for row in reader]
    except Exception as e:
        logger.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        return []

def write_csv_file(file_path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> bool:
    """
    辞書のリストをCSVファイルに書き込む
    
    Args:
        file_path (str): 出力先のCSVファイルパス
        data (List[Dict[str, Any]]): 書き込むデータ（辞書のリスト）
        fieldnames (Optional[List[str]]): カラム名のリスト（Noneの場合は最初の辞書のキーを使用）
        
    Returns:
        bool: 成功した場合はTrue、失敗した場合はFalse
    """
    if not data:
        logger.warning("書き込むデータがありません")
        return False
    
    if not fieldnames:
        fieldnames = list(data[0].keys())
    
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"CSVファイルを保存しました: {file_path}")
        return True
    except Exception as e:
        logger.error(f"CSVファイルの書き込み中にエラーが発生しました: {e}")
        return False

def validate_required_fields(record: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
    """
    必須フィールドのバリデーションを行う
    
    Args:
        record (Dict[str, Any]): 検証するレコード
        required_fields (List[str]): 必須フィールドのリスト
        
    Returns:
        Tuple[bool, List[str]]: (バリデーション結果, エラーメッセージのリスト)
    """
    is_valid = True
    errors = []
    
    for field in required_fields:
        if field not in record or not str(record.get(field, '')).strip():
            is_valid = False
            errors.append(f"必須フィールドが不足しています: {field}")
    
    return is_valid, errors

def parse_coordinate(coord: str) -> Optional[float]:
    """
    座標文字列を浮動小数点数に変換する
    
    Args:
        coord (str): 座標文字列（例: "35.6895" または "139.6917"）
        
    Returns:
        Optional[float]: 変換された座標値（変換できない場合はNone）
    """
    if not coord:
        return None
    
    try:
        return float(coord)
    except (ValueError, TypeError):
        logger.warning(f"座標の形式が不正です: {coord}")
        return None

def parse_int(value: str) -> Optional[int]:
    """
    文字列を整数に変換する
    
    Args:
        value (str): 変換する文字列
        
    Returns:
        Optional[int]: 変換された整数値（変換できない場合はNone）
    """
    if not value:
        return None
    
    try:
        return int(float(value))
    except (ValueError, TypeError):
        logger.warning(f"整数に変換できません: {value}")
        return None

def parse_float(value: str) -> Optional[float]:
    """
    文字列を浮動小数点数に変換する
    
    Args:
        value (str): 変換する文字列
        
    Returns:
        Optional[float]: 変換された浮動小数点数（変換できない場合はNone）
    """
    if not value:
        return None
    
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"数値に変換できません: {value}")
        return None
