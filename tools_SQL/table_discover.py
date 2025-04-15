import streamlit as st
import pandas as pd
# Assuming core and tools_tableau are siblings under the main project root
from core.db_connector import get_redshift_data, get_postgres_data, get_mysql_data
from core.llm_services import LLMClientInterface # Adjusted path
import numpy as np

# --- Database Helper Functions ---

DB_FUNCTIONS = {
    "Redshift": get_redshift_data,
    "PostgreSQL": get_postgres_data,
    "MySQL": get_mysql_data,
}

# Database-specific queries for TABLES
TABLE_SCHEMA_QUERIES = {
    "Redshift": "SELECT \"column\" AS column_name, type AS data_type FROM pg_table_def WHERE schemaname = %s AND tablename = %s ORDER BY \"column\";",
    "PostgreSQL": "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s AND table_schema NOT IN ('information_schema', 'pg_catalog') ORDER BY ordinal_position;",
    "MySQL": "SELECT COLUMN_NAME as column_name, DATA_TYPE as data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION;",
}

# Database-specific queries for VIEWS
# 修改 Redshift 的 VIEW 查詢為確認可用的 svv_columns 版本
VIEW_SCHEMA_QUERIES = {
     "Redshift": """
        SELECT column_name, data_type
        FROM svv_columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position;
     """,
    "PostgreSQL": "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s AND table_schema NOT IN ('information_schema', 'pg_catalog') ORDER BY ordinal_position;",
    "MySQL": "SELECT COLUMN_NAME as column_name, DATA_TYPE as data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION;",
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
        return pd.DataFrame()

# Modified to accept object_type
def get_object_schema(db_type, schema_name, object_name, object_type='TABLE'):
    """Fetches the schema (column names and data types) for a table or view."""
    if object_type == 'TABLE':
        query_dict = TABLE_SCHEMA_QUERIES
    elif object_type == 'VIEW':
        query_dict = VIEW_SCHEMA_QUERIES
    else:
        st.error(f"不支援的物件類型: {object_type}")
        return pd.DataFrame()

    query = query_dict.get(db_type)
    if not query:
        st.error(f"不支援取得 {db_type} 的 {object_type} schema 資訊。")
        return pd.DataFrame()

    # 傳遞 schema_name 和 object_name 作為參數
    return run_query(db_type, query, (schema_name, object_name))

# Modified to accept object_name and type for clarity, though query is same
def get_object_row_count(db_type, schema_name, object_name, object_type='TABLE'):
    """Gets the total row count of a table or view."""
    # Combine schema and object name for the query, ensuring proper quoting if needed
    # Basic validation: Check if schema and object names are reasonably safe
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not schema_name or not all(c in allowed_chars for c in schema_name):
        st.error(f"無效的 Schema 名稱: {schema_name}")
        return None
    if not object_name or not all(c in allowed_chars for c in object_name):
         st.error(f"無效的物件名稱: {object_name}")
         return None

    # Construct qualified name (basic quoting for safety, might need adjustment based on DB rules)
    qualified_name = f"\"{schema_name}\".\"{object_name}\"" # Add quotes for Redshift/Postgres

    if object_type == 'VIEW':
        st.warning(f"正在計算 VIEW '{qualified_name}' 的總筆數，這可能會花費較長時間...", icon="⏳")

    query = f"SELECT COUNT(*) as total_rows FROM {qualified_name};"
    df = run_query(db_type, query)
    if not df.empty and pd.notna(df['total_rows'][0]):
        return df['total_rows'][0]
    return None # Return None if count fails or is NaN

# --- Data Type Mapping ---
# (map_data_type function remains the same)
def map_data_type(db_type_str):
    """Maps database-specific data types to general categories."""
    db_type_str = db_type_str.lower()
    if any(t in db_type_str for t in ['timestamp', 'date', 'time']):
        return 'datetime'
    if any(t in db_type_str for t in ['int', 'numeric', 'decimal', 'float', 'double', 'real', 'long', 'bigint', 'smallint', 'integer']):
        return 'numeric'
    if any(t in db_type_str for t in ['char', 'text', 'string', 'varchar', 'nvarchar']):
        return 'string'
    if 'bool' in db_type_str:
        return 'boolean'
    return 'other'

# --- EDA Helper Functions ---
# (analyze_* functions remain largely the same, accepting object_name)
# Modified signatures to accept object_name and type
def analyze_datetime_column(db_type, schema_name, object_name, column_name, object_type):
    """Performs EDA for datetime columns."""
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not column_name or not all(c in allowed_chars for c in column_name):
         st.error(f"無效的欄位名稱: {column_name}")
         return
    if not schema_name or not all(c in allowed_chars for c in schema_name):
        st.error(f"無效的 Schema 名稱: {schema_name}")
        return
    if not object_name or not all(c in allowed_chars for c in object_name):
         st.error(f"無效的物件名稱: {object_name}")
         return

    qualified_name = f"\"{schema_name}\".\"{object_name}\""
    # Use qualified name in queries
    query_stats = f"SELECT MIN(\"{column_name}\") as min_date, MAX(\"{column_name}\") as max_date FROM {qualified_name};"
    df_stats = run_query(db_type, query_stats)

    if not df_stats.empty:
        min_d = df_stats['min_date'][0]
        max_d = df_stats['max_date'][0]
        st.metric("最早日期", str(min_d) if pd.notna(min_d) else "N/A")
        st.metric("最晚日期", str(max_d) if pd.notna(max_d) else "N/A")

    # Monthly distribution using qualified name
    date_trunc_options = {
        "PostgreSQL": f"SELECT date_trunc('month', \"{column_name}\")::date as month_start, COUNT(*) as count FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL GROUP BY 1 ORDER BY 1;",
        "Redshift": f"SELECT date_trunc('month', \"{column_name}\")::date as month_start, COUNT(*) as count FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL GROUP BY 1 ORDER BY 1;",
        "MySQL": f"SELECT DATE_FORMAT(`{column_name}`, '%Y-%m-01') as month_start, COUNT(*) as count FROM `{schema_name}`.`{object_name}` WHERE `{column_name}` IS NOT NULL GROUP BY 1 ORDER BY 1;" # MySQL uses backticks
    }
    query_dist = date_trunc_options.get(db_type)
    if query_dist:
        df_dist = run_query(db_type, query_dist)
        if not df_dist.empty:
            st.write("#### 每月資料筆數分佈")
            # Ensure month_start is suitable for indexing (string or datetime)
            try:
                df_dist['month_start'] = pd.to_datetime(df_dist['month_start']).dt.strftime('%Y-%m')
            except Exception:
                df_dist['month_start'] = df_dist['month_start'].astype(str) # Fallback to string
            df_dist.set_index('month_start', inplace=True)
            st.bar_chart(df_dist['count'])
        else:
            st.write("無法計算每月分佈。")
    else:
        st.write(f"不支援 {db_type} 的每月分佈查詢。")

def analyze_numeric_column(db_type, schema_name, object_name, column_name, object_type):
    """Performs EDA for numeric columns."""
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not column_name or not all(c in allowed_chars for c in column_name):
         st.error(f"無效的欄位名稱: {column_name}")
         return
    if not schema_name or not all(c in allowed_chars for c in schema_name):
        st.error(f"無效的 Schema 名稱: {schema_name}")
        return
    if not object_name or not all(c in allowed_chars for c in object_name):
         st.error(f"無效的物件名稱: {object_name}")
         return

    qualified_name = f"\"{schema_name}\".\"{object_name}\""
    query_stats = f"SELECT MIN(\"{column_name}\") as min_val, MAX(\"{column_name}\") as max_val, AVG(\"{column_name}\"::float) as avg_val FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL;" # Cast avg to float for wider compatibility
    df_stats = run_query(db_type, query_stats)

    if not df_stats.empty:
        col1, col2, col3 = st.columns(3)
        min_v = df_stats['min_val'][0]
        max_v = df_stats['max_val'][0]
        avg_v = df_stats['avg_val'][0]
        col1.metric("最小值", f"{min_v:,.2f}" if pd.notna(min_v) else "N/A")
        col2.metric("最大值", f"{max_v:,.2f}" if pd.notna(max_v) else "N/A")
        col3.metric("平均值", f"{avg_v:,.2f}" if pd.notna(avg_v) else "N/A")

    st.write("#### 數值分佈圖 (抽樣前 10000 筆非空值)")
    query_sample = f"SELECT \"{column_name}\" FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL LIMIT 10000;"
    df_sample = run_query(db_type, query_sample)

    if not df_sample.empty:
        try:
            numeric_data = pd.to_numeric(df_sample[column_name], errors='coerce').dropna()
            if not numeric_data.empty:
                counts, bins = np.histogram(numeric_data, bins=10)
                bin_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(len(bins)-1)]
                hist_df = pd.DataFrame({'count': counts}, index=bin_labels)
                st.bar_chart(hist_df)
            else:
                 st.write("欄位資料無法轉換為數值進行分佈分析。")
        except Exception as e:
            st.warning(f"繪製數值分佈圖時發生錯誤: {e}")
    else:
        st.write("無法取得數值樣本資料。")

def analyze_string_column(db_type, schema_name, object_name, column_name, object_type):
    """Performs EDA for string columns."""
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not column_name or not all(c in allowed_chars for c in column_name):
         st.error(f"無效的欄位名稱: {column_name}")
         return
    if not schema_name or not all(c in allowed_chars for c in schema_name):
        st.error(f"無效的 Schema 名稱: {schema_name}")
        return
    if not object_name or not all(c in allowed_chars for c in object_name):
         st.error(f"無效的物件名稱: {object_name}")
         return

    qualified_name = f"\"{schema_name}\".\"{object_name}\""
    query_distinct_count = f"SELECT COUNT(DISTINCT \"{column_name}\") as distinct_count FROM {qualified_name};"
    df_distinct_count = run_query(db_type, query_distinct_count)
    distinct_count = 0
    if not df_distinct_count.empty and pd.notna(df_distinct_count['distinct_count'][0]):
        distinct_count = df_distinct_count['distinct_count'][0]

    st.metric("不重複值數量", distinct_count)

    if distinct_count == 0:
        st.write("欄位無資料或皆為 NULL。")
        return

    if 0 < distinct_count <= 30:
        st.write("#### 值分佈 (Top 30)")
        query_counts = f"SELECT \"{column_name}\", COUNT(*) as count FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL GROUP BY \"{column_name}\" ORDER BY count DESC LIMIT 30;"
        df_counts = run_query(db_type, query_counts)
        if not df_counts.empty:
            total_rows_non_null = df_counts['count'].sum()
            df_counts['佔比 (%)'] = (df_counts['count'] / total_rows_non_null * 100).round(2) if total_rows_non_null > 0 else 0
            # Handle potential non-string index values if column has mixed types wrongly classified as string
            try:
                df_counts.set_index(column_name, inplace=True)
            except Exception:
                 df_counts = df_counts.astype({column_name: str}) # Convert index column to string
                 df_counts.set_index(column_name, inplace=True)

            st.dataframe(df_counts)
            st.bar_chart(df_counts['count'])
        else:
             st.write("無法取得值分佈資料。")
    else: # distinct_count > 30 or distinct_count == 0 (already handled)
        st.write(f"#### 隨機樣本 (30 筆)")
        st.info(f"由於不重複值數量 ({distinct_count}) 過多，僅顯示隨機樣本。")
        query_sample = f"SELECT DISTINCT \"{column_name}\" FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL LIMIT 30;"
        df_sample = run_query(db_type, query_sample)
        if not df_sample.empty:
            st.dataframe(df_sample)
        else:
             st.write("無法取得樣本資料。")

def analyze_boolean_column(db_type, schema_name, object_name, column_name, object_type):
    """Performs EDA for boolean columns."""
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not column_name or not all(c in allowed_chars for c in column_name):
         st.error(f"無效的欄位名稱: {column_name}")
         return
    if not schema_name or not all(c in allowed_chars for c in schema_name):
        st.error(f"無效的 Schema 名稱: {schema_name}")
        return
    if not object_name or not all(c in allowed_chars for c in object_name):
         st.error(f"無效的物件名稱: {object_name}")
         return

    qualified_name = f"\"{schema_name}\".\"{object_name}\""
    st.write("#### 值分佈")
    query_counts = f"SELECT \"{column_name}\", COUNT(*) as count FROM {qualified_name} WHERE \"{column_name}\" IS NOT NULL GROUP BY \"{column_name}\";"
    df_counts = run_query(db_type, query_counts)

    if not df_counts.empty:
        total_rows_non_null = df_counts['count'].sum()
        df_counts['佔比 (%)'] = (df_counts['count'] / total_rows_non_null * 100).round(2) if total_rows_non_null > 0 else 0
        df_counts[column_name] = df_counts[column_name].astype(str)
        df_counts.set_index(column_name, inplace=True)
        st.dataframe(df_counts)
        st.bar_chart(df_counts['count'])
    else:
        st.write("無法取得值分佈資料。")


# --- LLM Helper Functions ---
# (generate_translation_prompt remains the same)
def generate_translation_prompt(column_name):
    """Generates prompt for translating column name."""
    return f"請將以下技術性的資料庫欄位名稱翻譯成在台灣常用的繁體中文業務意義，請盡量簡短，只回傳翻譯結果：\n欄位名稱：{column_name}\n可能的意義："

# Modified to include object type
def generate_relations_prompt(schema_df, object_type):
    """Generates prompt for suggesting related columns."""
    schema_str = "\n".join([f"- {row['column_name']} ({row['data_type']})" for index, row in schema_df.iterrows()])
    return f"""
    以下是一個資料庫 {object_type} 的欄位及其資料類型：
    {schema_str}

    請根據這些欄位名稱和類型，推測並建議哪些欄位之間可能存在關聯性（例如主外鍵、時間序列、分類關係），或者哪些欄位組合在一起分析可能會有意義。請用繁體中文簡短解釋原因。

    可能的關聯或組合建議：
    """

# --- Main Streamlit Function ---
def show(llm_client: LLMClientInterface, model_name: str):
    """主函數，顯示資料表探索工具的介面與邏輯。"""
    st.markdown("##### 資料表/視圖 探索工具")
    st.write("選擇資料庫、物件類型、Schema 和名稱，探索其結構、基本資訊和欄位內容分佈。")

    # --- Inputs ---
    col1, col2 = st.columns(2)
    with col1:
        db_type = st.selectbox("選擇資料庫類型", options=list(DB_FUNCTIONS.keys()))
    with col2:
        object_type = st.radio("選擇物件類型", ('TABLE', 'VIEW'), horizontal=True)

    # 新增 Schema 輸入
    schema_name = st.text_input("輸入 Schema 名稱", value="", help="物件所在的 Schema 名稱，例如 public")
    object_name = st.text_input(f"輸入要探索的 {object_type} 名稱", help=f"請輸入 {schema_name} 中的 {object_type} 名稱，注意區分大小寫。")

    if st.button(f"🚀 開始探索 {object_type}", type="primary"):
        if not db_type: st.warning("請選擇資料庫類型。"); st.stop()
        if not schema_name: st.warning("請輸入 Schema 名稱。"); st.stop() # 檢查 Schema 名稱
        if not object_name: st.warning(f"請輸入 {object_type} 名稱。"); st.stop()

        with st.spinner(f"正在連接 {db_type} 並讀取 {object_type} '{schema_name}.{object_name}' 資訊..."):
            # --- 1. 基礎資訊 & Schema ---
            st.markdown("---")
            st.markdown(f"### 1. {object_type} 基礎資訊 & 欄位結構")

            # 傳遞 schema_name
            row_count = get_object_row_count(db_type, schema_name, object_name, object_type)
            st.metric("總資料筆數", f"{row_count:,}" if row_count is not None else "計算失敗/過久")

            # 傳遞 schema_name
            schema_df = get_object_schema(db_type, schema_name, object_name, object_type)

            if schema_df.empty:
                st.error(f"無法讀取 {object_type} '{schema_name}.{object_name}' 的結構，請確認名稱、權限和物件類型。")
                st.stop()

            st.write(f"總欄位數: {len(schema_df)}")

            # --- LLM Translation ---
            translations = []
            meanings_placeholder = st.empty()
            with st.spinner("正在透過 AI 推測欄位意義..."):
                if llm_client and model_name:
                    for index, row in schema_df.iterrows():
                        try:
                            prompt = generate_translation_prompt(row['column_name'])
                            translation = llm_client.generate_text(prompt, model_name, temperature=0.1)
                            translations.append(translation.strip())
                        except Exception as e:
                            print(f"翻譯欄位 {row['column_name']} 時發生錯誤: {e}")
                            translations.append("翻譯失敗")
                    meanings_placeholder.success("欄位意義推測完成！")
                    schema_df['推測意義 (AI)'] = translations
                else:
                    meanings_placeholder.warning("LLM 服務未配置，無法進行欄位意義推測。")
                    schema_df['推測意義 (AI)'] = "N/A"

            schema_df['通用類型'] = schema_df['data_type'].apply(map_data_type)
            st.dataframe(schema_df)

            # --- LLM Relations Suggestion ---
            st.markdown("---")
            st.markdown("### 2. 欄位關聯性建議 (AI)")
            with st.spinner("正在透過 AI 分析欄位間可能的關聯..."):
                 if llm_client and model_name:
                     try:
                         relations_prompt = generate_relations_prompt(schema_df, object_type)
                         relations_suggestion = llm_client.generate_text(relations_prompt, model_name, temperature=0.5)
                         st.markdown(relations_suggestion)
                     except Exception as e:
                         st.error(f"分析欄位關聯性時發生錯誤: {e}")
                 else:
                     st.warning("LLM 服務未配置，無法進行欄位關聯建議。")

            # --- EDA Section ---
            st.markdown("---")
            st.markdown("### 3. 欄位探索性分析 (EDA)")
            st.info("點擊展開各欄位查看詳細分析。")

            if not schema_df.empty:
                for index, row in schema_df.iterrows():
                    col_name = row['column_name']
                    col_db_type = row['data_type']
                    col_general_type = row['通用類型']

                    with st.expander(f"欄位: **{col_name}** (類型: {col_db_type} / {col_general_type})"):
                        # 傳遞 schema_name 給 analyze 函數
                        with st.spinner(f"正在分析欄位 {col_name}..."):
                            try:
                                if col_general_type == 'datetime':
                                    analyze_datetime_column(db_type, schema_name, object_name, col_name, object_type)
                                elif col_general_type == 'numeric':
                                    analyze_numeric_column(db_type, schema_name, object_name, col_name, object_type)
                                elif col_general_type == 'string':
                                    analyze_string_column(db_type, schema_name, object_name, col_name, object_type)
                                elif col_general_type == 'boolean':
                                    analyze_boolean_column(db_type, schema_name, object_name, col_name, object_type)
                                else:
                                    st.write("此資料類型尚不支援自動 EDA 分析。")
                            except Exception as e:
                                st.error(f"分析欄位 '{col_name}' 時發生錯誤: {e}")
            else:
                st.warning("無法執行 EDA，因為未能讀取資料表/視圖結構。")