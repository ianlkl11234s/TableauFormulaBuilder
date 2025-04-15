import streamlit as st

def generate_boolean_formula(field_name):
    """根據欄位名稱生成 IIF 公式"""
    if not field_name or not field_name.strip():
        return None
    # 基本的清理，移除可能的括號
    clean_field_name = field_name.strip().replace("[", "").replace("]", "")
    # 加上 Tableau 欄位引用的括號
    tableau_field = f"[{clean_field_name}]"
    # 生成標籤名稱，移除常見的前綴或後綴
    label_name = clean_field_name
    common_prefixes = ["is_", "has_"]
    common_suffixes = ["_flag", "_ind"]
    for prefix in common_prefixes:
        if label_name.lower().startswith(prefix):
            label_name = label_name[len(prefix):]
            break
    for suffix in common_suffixes:
        if label_name.lower().endswith(suffix):
            label_name = label_name[:-len(suffix)]
            break
    label_name = label_name.replace("_", " ").strip().capitalize() # 簡單格式化

    formula = f"// 計算欄位名稱：是否有 {label_name}\n"
    formula += f"IIF(IFNULL({tableau_field}, 0) > 0, '有{label_name}', '無{label_name}')"
    return formula

def show():
    """顯示是否標籤工具的介面和邏輯"""
    st.markdown("""
    這個工具可以快速生成 Tableau 計算欄位，用來判斷某個欄位的值是否大於 0，並給予對應的「有/無」標籤。
    - 若欄位值為 `NULL`，會被視為 `0`。
    - 請在下方輸入欄位名稱，**每行一個**。
    """)

    field_names_input = st.text_area(
        "輸入欄位名稱 (每行一個)",
        value="coupon\ndiscount\npoint\n[訂單金額]\nhas_special_offer",
        height=150,
        help="例如：`coupon`, `[訂單折扣]`, `is_vip`"
    )

    if st.button("🏷️ 產生標籤計算式", type="primary"):
        field_names = [name.strip() for name in field_names_input.split("\n") if name.strip()]

        if not field_names:
            st.warning("請至少輸入一個欄位名稱。")
            st.stop()

        st.markdown("---")
        st.markdown("### 產生的 Tableau 計算式")

        results = []
        for name in field_names:
            formula = generate_boolean_formula(name)
            if formula:
                results.append(formula)

        if results:
            full_code = "\n\n".join(results)
            st.code(full_code, language="sql")

            # 複製按鈕 (使用 streamlit-copy-button)
            # from streamlit_copy_button import copy_button
            # copy_button(full_code, "📋 複製所有計算式")
        else:
            st.info("沒有產生任何計算式。請檢查輸入的欄位名稱。")
