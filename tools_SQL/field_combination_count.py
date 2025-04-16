import streamlit as st
import pandas as pd
# 確保使用正確的絕對導入路徑
from core.db_connector import get_redshift_data, get_postgres_data, get_mysql_data
# 可能需要從 table_discover 導入一些輔助函數，或者在這裡重新定義
from tools_SQL.table_discover import DB_FUNCTIONS, get_db_function, run_query, get_object_schema, map_data_type # 假設這些函數在同目錄的 table_discover.py 中

# 定義日期欄位的處理選項
DATE_TRUNC_OPTIONS = {
    "天": {
        "Redshift": "DATE_TRUNC('day', {})",
        "PostgreSQL": "DATE_TRUNC('day', {})",
        "MySQL": "DATE({})"
    },
    "週": {
        "Redshift": "DATE_TRUNC('week', {})",
        "PostgreSQL": "DATE_TRUNC('week', {})",
        "MySQL": "DATE(DATE_SUB({}, INTERVAL WEEKDAY({}) DAY))"
    },
    "月": {
        "Redshift": "DATE_TRUNC('month', {})",
        "PostgreSQL": "DATE_TRUNC('month', {})",
        "MySQL": "DATE_FORMAT({}, '%Y-%m-01')"
    },
    "年": {
        "Redshift": "DATE_TRUNC('year', {})",
        "PostgreSQL": "DATE_TRUNC('year', {})",
        "MySQL": "DATE_FORMAT({}, '%Y-01-01')"
    }
}

# --- Main Streamlit Function ---
def show():
    """主函數，顯示欄位組合計數工具的介面與邏輯。"""
    st.markdown("##### 欄位組合計數工具")
    st.write("選擇資料庫、物件和欄位，計算不同欄位值組合的出現次數。")

    # --- Session State Initialization ---
    # 使用 Session State 來保存 schema 和結果，避免重複載入
    if 'fc_schema_df' not in st.session_state:
        st.session_state.fc_schema_df = pd.DataFrame()
    if 'fc_selected_columns' not in st.session_state:
        st.session_state.fc_selected_columns = []
    if 'fc_date_options' not in st.session_state:
        st.session_state.fc_date_options = {}
    if 'fc_combination_results' not in st.session_state:
        st.session_state.fc_combination_results = pd.DataFrame()
    if 'fc_last_run_key' not in st.session_state: # 用來追蹤上次運行的輸入，避免不必要的重跑
        st.session_state.fc_last_run_key = ""

    # --- Inputs ---
    with st.container(border=True):
        st.markdown("###### 1. 選擇資料來源")
        col1, col2 = st.columns(2)
        with col1:
            db_type = st.selectbox("選擇資料庫類型", options=list(DB_FUNCTIONS.keys()), key="fc_db_type")
        with col2:
            object_type = st.radio("選擇物件類型", ('TABLE', 'VIEW'), horizontal=True, key="fc_object_type")

        schema_name = st.text_input("輸入 Schema 名稱", value="", help="物件所在的 Schema 名稱，例如 public, dbt_prod。", key="fc_schema_name")
        object_name = st.text_input(f"輸入要探索的 {object_type} 名稱", help=f"請輸入 {schema_name} 中的 {object_type} 名稱，注意區分大小寫。", key="fc_object_name")

        # 清除狀態的按鈕
        if st.button("清除狀態並重新載入 Schema", key="fc_clear_state"):
            st.session_state.fc_schema_df = pd.DataFrame()
            st.session_state.fc_selected_columns = []
            st.session_state.fc_date_options = {}
            st.session_state.fc_combination_results = pd.DataFrame()
            st.session_state.fc_last_run_key = ""
            st.rerun() # 重新運行以更新介面

    # --- Schema Loading and Column Selection ---
    if schema_name and object_name:
        # 只有在 schema 或 object name 改變時才重新載入 schema
        current_schema_key = f"{db_type}-{schema_name}-{object_name}-{object_type}"
        if st.session_state.fc_schema_df.empty or st.session_state.get('fc_current_schema_key') != current_schema_key:
            with st.spinner(f"正在讀取 {object_type} '{schema_name}.{object_name}' 的欄位結構..."):
                # 確保傳遞了 schema_name
                schema_df = get_object_schema(db_type, schema_name, object_name, object_type)
                # 增加通用類型判斷
                schema_df['通用類型'] = schema_df['data_type'].apply(map_data_type)
                st.session_state.fc_schema_df = schema_df
                st.session_state.fc_selected_columns = [] # 清空上次的選擇
                st.session_state.fc_date_options = {} # 清空日期欄位選項
                st.session_state.fc_combination_results = pd.DataFrame() # 清空上次的結果
                st.session_state.fc_last_run_key = ""
                st.session_state.fc_current_schema_key = current_schema_key # 記錄當前載入的 schema key
                if st.session_state.fc_schema_df.empty:
                     st.error(f"無法讀取 {object_type} '{schema_name}.{object_name}' 的結構，請確認輸入。")
                     st.stop()
                else:
                     st.success("欄位結構載入成功！請選擇要組合的欄位。")


        if not st.session_state.fc_schema_df.empty:
            with st.container(border=True):
                st.markdown("###### 2. 選擇要組合的欄位")
                all_columns = st.session_state.fc_schema_df['column_name'].tolist()

                # 使用 Multiselect 讓使用者勾選欄位
                selected_columns = st.multiselect(
                    "選擇欄位進行 Group By:",
                    options=all_columns,
                    default=st.session_state.fc_selected_columns, # 保留上次選擇
                    key="fc_multiselect"
                )
                # 更新 session state 中的選擇
                st.session_state.fc_selected_columns = selected_columns

                # 檢查是否有日期類型的欄位被選擇
                datetime_columns = []
                if selected_columns:
                    # 找出所有被選中的日期類型欄位
                    for col in selected_columns:
                        col_type = st.session_state.fc_schema_df.loc[
                            st.session_state.fc_schema_df['column_name'] == col, '通用類型'].values[0]
                        if col_type == 'datetime':
                            datetime_columns.append(col)

                # 為每個日期欄位提供日期粒度選項
                if datetime_columns:
                    st.subheader("日期欄位處理選項")
                    st.info("對於日期類型欄位，您可以選擇日期粒度：")
                    
                    # 初始化日期選項字典（如果是新選中的欄位）
                    for col in datetime_columns:
                        if col not in st.session_state.fc_date_options:
                            st.session_state.fc_date_options[col] = "月"  # 預設為月
                    
                    # 移除不再使用的欄位
                    for col in list(st.session_state.fc_date_options.keys()):
                        if col not in datetime_columns:
                            del st.session_state.fc_date_options[col]
                    
                    # 為每個日期欄位建立選擇器
                    date_cols = st.columns(min(3, len(datetime_columns)))  # 每行最多3個
                    for i, col in enumerate(datetime_columns):
                        with date_cols[i % len(date_cols)]:
                            st.session_state.fc_date_options[col] = st.selectbox(
                                f"{col} 日期粒度",
                                options=["天", "週", "月", "年"],
                                index=["天", "週", "月", "年"].index(st.session_state.fc_date_options[col]),
                                key=f"date_option_{col}"
                            )

                if st.button("📊 計算組合數量", type="primary", key="fc_run_button", disabled=not selected_columns):
                    if not selected_columns:
                        st.warning("請至少選擇一個欄位。")
                    else:
                         run_combination_query = True
                         # 檢查是否需要重新運行（選擇的欄位是否改變）
                         current_run_key = f"{db_type}-{schema_name}-{object_name}-{'-'.join(sorted(selected_columns))}-{str(st.session_state.fc_date_options)}"
                         if current_run_key == st.session_state.fc_last_run_key:
                              st.info("使用快取結果。如需重新計算，請更改欄位選擇或清除狀態。")
                              run_combination_query = False

                         if run_combination_query:
                            with st.spinner(f"正在計算 {len(selected_columns)} 個欄位的組合數量..."):
                                # --- Construct and Run Query ---
                                # 確保欄位名稱被正確引用 (例如 Redshift/PG 用雙引號, MySQL 用反引號)
                                quote_char_start, quote_char_end = ('"', '"') if db_type in ["Redshift", "PostgreSQL"] else ('`', '`')
                                
                                # 處理選定的欄位，包括日期欄位的特殊處理
                                select_columns = []
                                group_by_columns = []
                                select_aliases = []
                                
                                for col in selected_columns:
                                    quoted_col = f"{quote_char_start}{col}{quote_char_end}"
                                    # 檢查是否為日期欄位
                                    col_type = st.session_state.fc_schema_df.loc[
                                        st.session_state.fc_schema_df['column_name'] == col, '通用類型'].values[0]
                                    
                                    if col_type == 'datetime' and col in st.session_state.fc_date_options:
                                        # 獲取選擇的日期粒度
                                        date_option = st.session_state.fc_date_options[col]
                                        # 根據數據庫類型和日期粒度，找到正確的 DATE_TRUNC 函數
                                        date_func_template = DATE_TRUNC_OPTIONS[date_option][db_type]
                                        date_func = date_func_template.format(quoted_col)
                                        
                                        # 使用別名以便在結果中顯示
                                        alias = f"{quote_char_start}{col}_{date_option}{quote_char_end}"
                                        select_columns.append(f"{date_func} AS {alias}")
                                        group_by_columns.append(f"{date_func}")
                                        select_aliases.append(alias)
                                    else:
                                        # 非日期欄位正常處理
                                        select_columns.append(quoted_col)
                                        group_by_columns.append(quoted_col)
                                        select_aliases.append(quoted_col)
                                
                                select_clause = ", ".join(select_columns) + ", COUNT(*) as count"
                                group_by_clause = ", ".join(group_by_columns)
                                
                                # 構建完整的物件名稱
                                qualified_name = f"\"{schema_name}\".\"{object_name}\"" if db_type in ["Redshift", "PostgreSQL"] else f"`{schema_name}`.`{object_name}`"
                                
                                # 構建 SQL 查詢：使用美觀的格式
                                sql_query = f"""SELECT 
                                                    {select_clause}
                                                FROM 
                                                    {qualified_name}
                                                GROUP BY 
                                                    {group_by_clause}
                                                ORDER BY 
                                                    count DESC;"""

                                st.session_state.fc_sql_query = sql_query # 保存查詢語句供顯示

                                # 執行查詢
                                results_df = run_query(db_type, sql_query)
                                
                                # 計算比例
                                if not results_df.empty and 'count' in results_df.columns:
                                    total_count = results_df['count'].sum()
                                    results_df['百分比'] = (results_df['count'] / total_count * 100).round(2).astype(str) + '%'
                                
                                st.session_state.fc_combination_results = results_df
                                st.session_state.fc_last_run_key = current_run_key # 記錄這次運行的 key


    # --- Display Results ---
    if not st.session_state.fc_combination_results.empty:
         with st.container(border=True):
             st.markdown("###### 3. 組合結果")
             # 計算總列數
             total_rows = len(st.session_state.fc_combination_results)
             total_count = st.session_state.fc_combination_results['count'].sum() if 'count' in st.session_state.fc_combination_results.columns else 0
             
             st.write(f"共有 {total_rows:,} 種不同組合，總計 {total_count:,} 筆資料")
             
             st.dataframe(st.session_state.fc_combination_results)
             
             # 顯示執行的 SQL (使用格式化的 SQL)
             with st.expander("查看執行的 SQL 查詢"):
                 st.code(st.session_state.get('fc_sql_query', '無法顯示 SQL'), language='sql')
             
             # 提供下載按鈕
             csv = st.session_state.fc_combination_results.to_csv(index=False).encode('utf-8')
             st.download_button(
                 label="下載結果 (CSV)",
                 data=csv,
                 file_name=f'{schema_name}_{object_name}_combinations.csv',
                 mime='text/csv',
                 key="fc_download_button"
             )
