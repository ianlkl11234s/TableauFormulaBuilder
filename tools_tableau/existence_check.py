import streamlit as st

def generate_existence_formula(field_name, label, condition_type="greater_than_zero", fallback="無"):
    """生成判斷欄位有無的公式"""
    if not field_name or not field_name.strip() or not label or not label.strip():
        return None
    
    # 清理欄位名稱
    field_name = field_name.strip()
    if not (field_name.startswith('[') and field_name.endswith(']')):
        field_name = f"[{field_name}]"
    
    # 清理標籤名稱，去除可能的「有」前綴
    label = label.strip()
    if label.startswith("有"):
        label = label[1:]
    
    # 根據條件類型生成不同的判斷條件
    if condition_type == "greater_than_zero":
        condition = f"{field_name} > 0"
        explanation = f"// 判斷 {field_name} 是否大於 0\n"
    elif condition_type == "not_null":
        condition = f"NOT ISNULL({field_name})"
        explanation = f"// 判斷 {field_name} 是否有值（不為 NULL）\n"
    elif condition_type == "not_empty":
        condition = f"NOT ISNULL({field_name}) AND {field_name} <> ''"
        explanation = f"// 判斷 {field_name} 是否有值且不為空字串\n"
    elif condition_type == "true":
        condition = field_name
        explanation = f"// 判斷 {field_name} 是否為 TRUE\n"
    else:
        # 預設為大於零
        condition = f"{field_name} > 0"
        explanation = f"// 判斷 {field_name} 是否大於 0\n"
    
    # 生成公式
    formula = explanation
    formula += f"// 處理 NULL 值：若結果為 NULL，則視為「無{label}」\n"
    formula += f"IFNULL(\n"
    formula += f"    IIF({condition}, '有{label}', '無{label}'),\n"
    formula += f"    '無{label}'\n"
    formula += f")"
    
    return formula

def show():
    """顯示有無判斷工具的介面和邏輯"""
    st.markdown("##### 有無判斷")
    st.write("""
    這個工具可以幫助您生成判斷欄位「有無」的計算欄位，常用於標記特定條件是否成立。
    例如：判斷是否有 OMO 訂單、是否有會員資料等。
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        field_name = st.text_input(
            "判斷欄位",
            value="[區間內_內掃訂單數]",
            help="要進行判斷的欄位，例如：[訂單數量]、[會員ID]"
        )
    
    with col2:
        label = st.text_input(
            "結果標籤",
            value="OMO",
            help="輸出時的標籤，將自動生成「有xxx」和「無xxx」格式"
        )
    
    st.markdown("---")
    st.markdown("##### 判斷條件")
    
    condition_type = st.radio(
        "選擇判斷條件",
        options=[
            "大於零 (> 0)",
            "非空值 (NOT ISNULL)",
            "非空字串 (NOT ISNULL AND <> '')",
            "為真 (= TRUE)"
        ],
        index=0,
        help="選擇判斷「有」的條件"
    )
    
    # 將選項映射到內部使用的值
    condition_map = {
        "大於零 (> 0)": "greater_than_zero",
        "非空值 (NOT ISNULL)": "not_null",
        "非空字串 (NOT ISNULL AND <> '')": "not_empty",
        "為真 (= TRUE)": "true"
    }
    
    selected_condition = condition_map[condition_type]
    
    # 高級選項
    st.markdown("---")
    st.markdown("##### 進階選項")
    
    custom_format = st.checkbox(
        "自訂輸出格式",
        value=False,
        help="勾選後可以自訂「有/無」的輸出格式"
    )
    
    if custom_format:
        col3, col4 = st.columns(2)
        with col3:
            true_prefix = st.text_input(
                "有的前綴",
                value="有",
                help="符合條件時的前綴詞"
            )
        with col4:
            false_prefix = st.text_input(
                "無的前綴",
                value="無",
                help="不符合條件時的前綴詞"
            )
    else:
        true_prefix = "有"
        false_prefix = "無"
    
    if st.button("🔍 產生有無判斷公式", type="primary"):
        if not field_name or not label:
            st.warning("請填寫判斷欄位和結果標籤。")
            st.stop()
        
        # 根據條件類型生成說明文字
        if selected_condition == "greater_than_zero":
            condition_explanation = f"判斷 {field_name} 是否大於 0"
            condition_display = f"{field_name} > 0"
        elif selected_condition == "not_null":
            condition_explanation = f"判斷 {field_name} 是否有值（不為 NULL）"
            condition_display = f"NOT ISNULL({field_name})"
        elif selected_condition == "not_empty":
            condition_explanation = f"判斷 {field_name} 是否有值且不為空字串"
            condition_display = f"NOT ISNULL({field_name}) AND {field_name} <> ''"
        elif selected_condition == "true":
            condition_explanation = f"判斷 {field_name} 是否為 TRUE"
            condition_display = field_name
        
        # 生成公式
        formula = f"// {condition_explanation}\n"
        formula += f"// 處理 NULL 值：若結果為 NULL，則視為「{false_prefix}{label}」\n"
        formula += f"IFNULL(\n"
        formula += f"    IIF({condition_display}, '{true_prefix}{label}', '{false_prefix}{label}'),\n"
        formula += f"    '{false_prefix}{label}'\n"
        formula += f")"
        
        st.success("✨ 公式已生成！")
        st.code(formula, language="sql")
        
        # 顯示範例說明
        st.markdown("##### 公式說明")
        
        st.markdown(f"""
        此公式{condition_explanation}：
        
        - 如果 `{condition_display}` 條件成立，則返回 **"{true_prefix}{label}"**
        - 否則返回 **"{false_prefix}{label}"**
        - 若計算結果為 NULL，也會返回 **"{false_prefix}{label}"**
        
        IFNULL 函數確保即使計算過程中出現 NULL 值，也能得到預期的結果而不是 NULL。
        """)