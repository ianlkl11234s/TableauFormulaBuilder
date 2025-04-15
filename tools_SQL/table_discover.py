import streamlit as st
import pandas as pd
from core.db_connector import get_redshift_data, get_postgres_data, get_mysql_data # Relative import
from tools_tableau.llm_services import LLMClientInterface # Relative import
import numpy as np # For potential histogram binning

# --- Database Helper Functions ---

DB_FUNCTIONS = {
    "PostgreSQL": get_postgres_data,
    "Redshift": get_redshift_data,
    "MySQL": get_mysql_data,
}

# Database-specific schema queries (adjust schema names if needed)
SCHEMA_QUERIES = {
    "PostgreSQL": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position;",
    "Redshift": "SELECT \"column\" AS column_name, type AS data_type FROM pg_table_def WHERE tablename = %s ORDER BY \"column\";", # Redshift uses pg_table_def
    "MySQL": "SELECT COLUMN_NAME as column_name, DATA_TYPE as data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s ORDER BY ORDINAL_POSITION;", # Assumes current database
}

def get_db_function(db_type):
    """Get the appropriate data fetching function based on db_type."""
    return DB_FUNCTIONS.get(db_type)

def run_query(db_type, sql_query, params=None):
    """Runs a query using the correct database function."""
    db_func = get_db_function(db_type)
    if not db_func:
        raise ValueError(f"Unsupported database type: {db_type}")
    try:
        return db_func(sql_query, params)
    except Exception as e:
        st.error(f"資料庫查詢錯誤 ({db_type}): {e}")
        # Optionally re-raise or return None/empty DataFrame
        # raise # Re-raise if you want the main function to handle it further
        return pd.DataFrame() # Return empty DataFrame to prevent further errors

def get_table_schema(db_type, table_name):
    """Fetches the table schema (column names and data types)."""
    query = SCHEMA_QUERIES.get(db_type)
    if not query:
        st.error(f"不支援取得 {db_type} 的 schema 資訊。")
        return pd.DataFrame()
    return run_query(db_type, query, (table_name,))

def get_row_count(db_type, table_name):
    """Gets the total row count of a table."""
    # Basic check for table name validity (prevent SQL injection)
    if not table_name or not table_name.isalnum() and '_' not in table_name:
         st.error(f"無效的表名稱: {table_name}")
         return 0
    # Use f-string carefully ONLY after validation, or prefer parameterized queries if connector supports it for table names (most don't)
    query = f"SELECT COUNT(*) as total_rows FROM {table_name};"
    df = run_query(db_type, query)
    if not df.empty:
        return df['total_rows'][0]
    return 0

# --- Data Type Mapping ---
def map_data_type(db_type_str):
    """Maps database-specific data types to general categories."""
    db_type_str = db_type_str.lower()
    if any(t in db_type_str for t in ['timestamp', 'date', 'time']):
        return 'datetime'
    if any(t in db_type_str for t in ['int', 'numeric', 'decimal', 'float', 'double', 'real', 'long']):
        return 'numeric'
    if any(t in db_type_str for t in ['char', 'text', 'string', 'varchar']):
        return 'string'
    if 'bool' in db_type_str:
        return 'boolean'
    return 'other'

# --- EDA Helper Functions ---

def analyze_datetime_column(db_type, table_name, column_name):
    """Performs EDA for datetime columns."""
    # Basic check for column name validity
    if not column_name or not column_name.isalnum() and '_' not in column_name:
         st.error(f"無效的欄位名稱: {column_name}")
         return

    query_stats = f"SELECT MIN({column_name}) as min_date, MAX({column_name}) as max_date FROM {table_name};"
    df_stats = run_query(db_type, query_stats)

    if not df_stats.empty:
        st.metric("最早日期", str(df_stats['min_date'][0]))
        st.metric("最晚日期", str(df_stats['max_date'][0]))

    # Monthly distribution (consider sampling for large tables)
    # Database-specific date truncation is more efficient than pulling all data
    date_trunc_options = {
        "PostgreSQL": f"SELECT date_trunc('month', {column_name})::date as month_start, COUNT(*) as count FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY 1 ORDER BY 1;",
        "Redshift": f"SELECT date_trunc('month', {column_name})::date as month_start, COUNT(*) as count FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY 1 ORDER BY 1;",
        "MySQL": f"SELECT DATE_FORMAT({column_name}, '%Y-%m-01') as month_start, COUNT(*) as count FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY 1 ORDER BY 1;"
    }
    query_dist = date_trunc_options.get(db_type)
    if query_dist:
        df_dist = run_query(db_type, query_dist)
        if not df_dist.empty:
            st.write("#### 每月資料筆數分佈")
            df_dist.set_index('month_start', inplace=True)
            st.bar_chart(df_dist['count'])
        else:
            st.write("無法計算每月分佈。")
    else:
        st.write(f"不支援 {db_type} 的每月分佈查詢。")


def analyze_numeric_column(db_type, table_name, column_name):
    """Performs EDA for numeric columns."""
    if not column_name or not column_name.isalnum() and '_' not in column_name:
         st.error(f"無效的欄位名稱: {column_name}")
         return

    # Basic stats
    query_stats = f"SELECT MIN({column_name}) as min_val, MAX({column_name}) as max_val, AVG({column_name}) as avg_val FROM {table_name} WHERE {column_name} IS NOT NULL;"
    df_stats = run_query(db_type, query_stats)

    if not df_stats.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("最小值", f"{df_stats['min_val'][0]:,.2f}" if pd.notna(df_stats['min_val'][0]) else "N/A")
        col2.metric("最大值", f"{df_stats['max_val'][0]:,.2f}" if pd.notna(df_stats['max_val'][0]) else "N/A")
        col3.metric("平均值", f"{df_stats['avg_val'][0]:,.2f}" if pd.notna(df_stats['avg_val'][0]) else "N/A")

    # Distribution (Histogram - Sample data for large tables)
    st.write("#### 數值分佈圖 (抽樣前 10000 筆非空值)")
    # Consider adding TABLESAMPLE if supported and needed for performance
    query_sample = f"SELECT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 10000;"
    df_sample = run_query(db_type, query_sample)

    if not df_sample.empty:
        try:
            # Attempt to convert to numeric, coercing errors
            numeric_data = pd.to_numeric(df_sample[column_name], errors='coerce').dropna()
            if not numeric_data.empty:
                # Simple histogram using numpy and st.bar_chart
                counts, bins = np.histogram(numeric_data, bins=10) # Adjust bins as needed
                bin_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(len(bins)-1)]
                hist_df = pd.DataFrame({'count': counts}, index=bin_labels)
                st.bar_chart(hist_df)
            else:
                 st.write("欄位資料無法轉換為數值進行分佈分析。")
        except Exception as e:
            st.warning(f"繪製數值分佈圖時發生錯誤: {e}")
    else:
        st.write("無法取得數值樣本資料。")


def analyze_string_column(db_type, table_name, column_name):
    """Performs EDA for string columns."""
    if not column_name or not column_name.isalnum() and '_' not in column_name:
         st.error(f"無效的欄位名稱: {column_name}")
         return

    # Get distinct count
    query_distinct_count = f"SELECT COUNT(DISTINCT {column_name}) as distinct_count FROM {table_name};"
    df_distinct_count = run_query(db_type, query_distinct_count)
    distinct_count = 0
    if not df_distinct_count.empty:
        distinct_count = df_distinct_count['distinct_count'][0]

    st.metric("不重複值數量", distinct_count)

    if distinct_count == 0:
        st.write("欄位無資料或皆為 NULL。")
        return

    if distinct_count <= 30:
        st.write("#### 值分佈 (Top 30)")
        query_counts = f"SELECT {column_name}, COUNT(*) as count FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY {column_name} ORDER BY count DESC LIMIT 30;"
        df_counts = run_query(db_type, query_counts)
        if not df_counts.empty:
            total_rows_non_null = df_counts['count'].sum() # Use sum of counts as total (approx if LIMIT < total)
            df_counts['佔比 (%)'] = (df_counts['count'] / total_rows_non_null * 100).round(2)
            df_counts.set_index(column_name, inplace=True)
            st.dataframe(df_counts)
            st.bar_chart(df_counts['count'])
        else:
             st.write("無法取得值分佈資料。")
    else:
        st.write(f"#### 隨機樣本 (30 筆)")
        st.info(f"由於不重複值數量 ({distinct_count}) 過多，僅顯示隨機樣本。")
        # Sampling method depends on DB. LIMIT is simple but not random.
        # ORDER BY RANDOM() is expensive. Use simple LIMIT for now.
        query_sample = f"SELECT DISTINCT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 30;"
        df_sample = run_query(db_type, query_sample)
        if not df_sample.empty:
            st.dataframe(df_sample)
        else:
             st.write("無法取得樣本資料。")

def analyze_boolean_column(db_type, table_name, column_name):
    """Performs EDA for boolean columns."""
    if not column_name or not column_name.isalnum() and '_' not in column_name:
         st.error(f"無效的欄位名稱: {column_name}")
         return

    st.write("#### 值分佈")
    query_counts = f"SELECT {column_name}, COUNT(*) as count FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY {column_name};"
    df_counts = run_query(db_type, query_counts)

    if not df_counts.empty:
        total_rows_non_null = df_counts['count'].sum()
        df_counts['佔比 (%)'] = (df_counts['count'] / total_rows_non_null * 100).round(2)
        # Ensure boolean values are displayed nicely
        df_counts[column_name] = df_counts[column_name].astype(str)
        df_counts.set_index(column_name, inplace=True)
        st.dataframe(df_counts)
        st.bar_chart(df_counts['count'])
    else:
        st.write("無法取得值分佈資料。")


# --- LLM Helper Functions ---
def generate_translation_prompt(column_name):
    """Generates prompt for translating column name."""
    return f"請將以下技術性的資料庫欄位名稱翻譯成在台灣常用的繁體中文業務意義，請盡量簡短，只回傳翻譯結果：\n欄位名稱：{column_name}\n可能的意義："

def generate_relations_prompt(schema_df):
    """Generates prompt for suggesting related columns."""
    schema_str = "\n".join([f"- {row['column_name']} ({row['data_type']})" for index, row in schema_df.iterrows()])
    return f"""
    以下是資料表中的欄位及其資料類型：
    {schema_str}

    請根據這些欄位名稱和類型，推測並建議哪些欄位之間可能存在關聯性，或者哪些欄位組合在一起分析可能會有意義。請用繁體中文簡短解釋原因。

    可能的關聯或組合建議：
    """

# --- Main Streamlit Function ---
def show(llm_client: LLMClientInterface, model_name: str):
    """主函數，顯示資料表探索工具的介面與邏輯。"""
    st.markdown("##### 資料表探索工具")
    st.write("選擇資料庫和表名，探索表的結構、基本資訊和欄位內容分佈。")

    # --- Inputs ---
    db_type = st.selectbox("選擇資料庫類型", options=list(DB_FUNCTIONS.keys()))
    table_name = st.text_input("輸入要探索的表名", help="請輸入資料庫中的表名，區分大小寫。")

    if st.button("🚀 開始探索", type="primary"):
        if not db_type:
            st.warning("請選擇資料庫類型。")
            st.stop()
        if not table_name:
            st.warning("請輸入表名。")
            st.stop()

        with st.spinner(f"正在連接 {db_type} 並讀取資料表資訊..."):
            # --- 1. 基礎資訊 & Schema ---
            st.markdown("---")
            st.markdown("### 1. 資料表基礎資訊 & 欄位結構")

            row_count = get_row_count(db_type, table_name)
            st.metric("總資料筆數", f"{row_count:,}")

            schema_df = get_table_schema(db_type, table_name)

            if schema_df.empty:
                st.error(f"無法讀取表 '{table_name}' 的結構，請確認表名和權限。")
                st.stop()

            st.write(f"總欄位數: {len(schema_df)}")

            # Get translations using LLM (add error handling)
            translations = []
            meanings_placeholder = st.empty() # Placeholder for status
            with st.spinner("正在透過 AI 推測欄位意義..."):
                for index, row in schema_df.iterrows():
                    try:
                        prompt = generate_translation_prompt(row['column_name'])
                        translation = llm_client.generate_text(prompt, model_name, temperature=0.1)
                        translations.append(translation.strip())
                    except Exception as e:
                        print(f"翻譯欄位 {row['column_name']} 時發生錯誤: {e}")
                        translations.append("翻譯失敗") # Append placeholder on error
                        # Optionally add a warning to the UI for the user
                meanings_placeholder.success("欄位意義推測完成！")

            schema_df['推測意義 (AI)'] = translations
            schema_df['通用類型'] = schema_df['data_type'].apply(map_data_type)

            st.dataframe(schema_df)


            # --- 5. 欄位關聯性建議 (LLM) ---
            st.markdown("---")
            st.markdown("### 2. 欄位關聯性建議 (AI)")
            with st.spinner("正在透過 AI 分析欄位間可能的關聯..."):
                 try:
                     relations_prompt = generate_relations_prompt(schema_df)
                     relations_suggestion = llm_client.generate_text(relations_prompt, model_name, temperature=0.5)
                     st.markdown(relations_suggestion)
                 except Exception as e:
                     st.error(f"分析欄位關聯性時發生錯誤: {e}")


            # --- 4. 欄位探索性資料分析 (EDA) ---
            st.markdown("---")
            st.markdown("### 3. 欄位探索性分析 (EDA)")
            st.info("點擊展開各欄位查看詳細分析。")

            if not schema_df.empty:
                for index, row in schema_df.iterrows():
                    col_name = row['column_name']
                    col_db_type = row['data_type']
                    col_general_type = row['通用類型']

                    with st.expander(f"欄位: **{col_name}** (類型: {col_db_type} / {col_general_type})"):
                        with st.spinner(f"正在分析欄位 {col_name}..."):
                            try:
                                if col_general_type == 'datetime':
                                    analyze_datetime_column(db_type, table_name, col_name)
                                elif col_general_type == 'numeric':
                                    analyze_numeric_column(db_type, table_name, col_name)
                                elif col_general_type == 'string':
                                    analyze_string_column(db_type, table_name, col_name)
                                elif col_general_type == 'boolean':
                                    analyze_boolean_column(db_type, table_name, col_name)
                                else:
                                    st.write("此資料類型尚不支援自動 EDA 分析。")
                            except Exception as e:
                                st.error(f"分析欄位 '{col_name}' 時發生錯誤: {e}")
            else:
                st.warning("無法執行 EDA，因為未能讀取資料表結構。")
