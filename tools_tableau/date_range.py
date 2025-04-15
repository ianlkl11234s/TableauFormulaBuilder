import streamlit as st

def generate_date_range_formula(date_field, reference_date, range_value, range_unit, include_equal=True):
    """生成日期區間比較公式"""
    if not date_field or not date_field.strip() or not reference_date or not reference_date.strip():
        return None
    
    # 清理欄位名稱（確保有方括號）
    date_field = date_field.strip()
    if not (date_field.startswith('[') and date_field.endswith(']')):
        date_field = f"[{date_field}]"
    
    reference_date = reference_date.strip()
    if not (reference_date.startswith('[') and reference_date.endswith(']')):
        reference_date = f"[{reference_date}]"
    
    # 根據是否包含等於生成比較運算符
    operator = "<=" if include_equal else "<"
    
    # 生成公式
    formula = f"// 判斷 {date_field} 是否在 {reference_date} 的 {range_value} {range_unit} 內\n"
    formula += f"IFNULL(IIF(DATEDIFF('{range_unit}', {date_field}, {reference_date}) {operator} {range_value}, 'Y', 'N'), 'N')"
    
    return formula

def show():
    """顯示日期區間工具的介面和邏輯"""
    st.markdown("##### 日期區間篩選")
    st.write("""
    這個工具可以幫助您生成判斷日期是否在特定區間內的計算欄位，常用於時間窗口分析。
    例如：判斷某個日期是否在參考日期的前30天內。
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_field = st.text_input(
            "日期欄位",
            value="[local_date]",
            help="要進行比較的日期欄位，例如：[訂單日期]、[註冊時間]"
        )
    
    with col2:
        reference_date = st.text_input(
            "參照日期",
            value="[參數].[data_time]",
            help="作為參考的日期，可以是欄位或參數，例如：[今天]、[參數].[查詢日期]"
        )
    
    # 區間設定
    col3, col4 = st.columns(2)
    
    with col3:
        range_value = st.number_input(
            "區間值",
            min_value=1,
            value=30,
            step=1,
            help="時間區間的數值，例如：7、30、90"
        )
    
    with col4:
        range_unit = st.selectbox(
            "時間單位",
            options=["day", "week", "month", "quarter", "year"],
            index=0,
            help="時間單位，影響 DATEDIFF 的第一個參數"
        )
    
    # 高級選項
    st.markdown("---")
    st.markdown("##### 進階選項")
    
    include_equal = st.checkbox(
        "包含等於（<=）",
        value=True,
        help="勾選表示使用 <= 運算符（包含邊界值），取消勾選表示使用 < 運算符（不包含邊界值）"
    )
    
    custom_format = st.checkbox(
        "自訂輸出格式",
        value=False,
        help="勾選後可以自訂 Y/N 以外的輸出格式"
    )
    
    if custom_format:
        col5, col6 = st.columns(2)
        with col5:
            true_value = st.text_input(
                "在區間內顯示值",
                value="在區間內",
                help="當日期在指定區間內時顯示的值"
            )
        with col6:
            false_value = st.text_input(
                "不在區間內顯示值",
                value="不在區間內",
                help="當日期不在指定區間內時顯示的值"
            )
    else:
        true_value = "Y"
        false_value = "N"
    
    if st.button("🔍 產生日期區間公式", type="primary"):
        if not date_field or not reference_date:
            st.warning("請填寫日期欄位和參照日期。")
            st.stop()
        
        # 生成基本公式
        formula = f"// 判斷 {date_field} 是否在 {reference_date} 的 {range_value} {range_unit} 內\n"
        
        # 運算符
        operator = "<=" if include_equal else "<"
        
        # 生成完整公式，包含自訂輸出值
        formula += f"""IFNULL(
        IIF(DATEDIFF('{range_unit}', {date_field}, {reference_date}) {operator} {range_value}, '{true_value}', '{false_value}')
        , '{false_value}')"""
        st.success("✨ 公式已生成！")
        st.code(formula, language="sql")


def range_unit_display(unit):
    """轉換單位為中文顯示"""
    units = {
        "day": "天",
        "week": "週",
        "month": "月",
        "quarter": "季",
        "year": "年"
    }
    return units.get(unit, unit)