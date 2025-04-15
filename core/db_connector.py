import redshift_connector
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 載入 .env 檔案中的環境變數
load_dotenv()

# 設定連線參數
REDSHIFT_CONFIG = {
    'host': os.getenv('REDSHIFT_HOST'),
    'database': os.getenv('REDSHIFT_DATABASE'),
    'user': os.getenv('REDSHIFT_USER'),
    'password': os.getenv('REDSHIFT_PASSWORD')
}

# PostgreSQL 連線參數
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'database': os.getenv('POSTGRES_DATABASE'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'port': os.getenv('POSTGRES_PORT')
}

# MySQL 連線參數
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST'),
    'database': os.getenv('MYSQL_DATABASE'), 
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'port': os.getenv('MYSQL_PORT')
}

def get_gsheet_data(sheet_name, worksheet_name):
    """從 Google Sheets 取得資料並返回 DataFrame"""
    if not all([sheet_name, worksheet_name]):
        print("sheet_name 和 worksheet_name 不能為空")
        return None
        
    try:
        # 設定 API 認證
        scope = ['https://spreadsheets.google.com/feeds', 
                'https://www.googleapis.com/auth/drive']
        
        key_path = os.getenv('GOOGLE_SHEET_KEY_PATH')
        if not key_path:
            raise ValueError("找不到 GOOGLE_SHEET_KEY_PATH 環境變數")
            
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
        client = gspread.authorize(creds)
        
        # 獲取試算表與工作表
        spreadsheet = client.open(sheet_name)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # 取得所有資料並轉換為 DataFrame
        data = worksheet.get_all_records()
        if not data:
            print("工作表中沒有資料")
            return pd.DataFrame()
            
        return pd.DataFrame(data)
        
    except Exception as e:
        print(f"從 Google Sheets 讀取資料時發生錯誤: {str(e)}")
        return None

# 建立連線函數
def get_redshift_data(sql_query, params=None):
    """執行 SQL 查詢並返回 DataFrame"""
    conn = redshift_connector.connect(**REDSHIFT_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query, params)
        column_names = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=column_names)
    finally:
        cursor.close()
        conn.close()


def get_postgres_data(sql_query, params=None):
    """執行 PostgreSQL 查詢並返回 DataFrame"""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    try:
        return pd.read_sql_query(sql_query, conn, params=params)
    finally:
        conn.close()


def get_mysql_data(sql_query, params=None):
    """執行 MySQL 查詢並返回 DataFrame"""
    import mysql.connector
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    try:
        return pd.read_sql_query(sql_query, conn, params=params)
    finally:
        conn.close()

