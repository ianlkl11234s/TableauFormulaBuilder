import streamlit as st
from openai import OpenAI, RateLimitError, AuthenticationError # 引入特定錯誤類型

def validate_group_logic(logic_str):
    """驗證分組邏輯的格式"""
    try:
        values = [x.strip() for x in logic_str.split(",")]
        if not values: return False, "輸入不可為空"
        if values[0].lower() != "null": return False, "第一個值必須是 null"
        if len(values) < 2 or values[1].lower() != "<0": return False, "第二個值必須是 <0"

        prev = -float('inf') # 允許第一個數字是 0 或負數
        for v in values[2:]:
            try:
                current = float(v)
                # 允許等於，因為可能會有 0, 0 的情況 (雖然 Tableau 通常不這樣用)
                # 但嚴格遞增比較常見，所以還是維持 current <= prev
                if current <= prev:
                    return False, f"數值必須依序嚴格遞增 (錯誤發生在: {prev} -> {current})"
                prev = current
            except ValueError:
                return False, f"'{v}' 不是有效的數字"
        return True, ""
    except Exception as e:
        return False, f"解析錯誤: {str(e)}"

def generate_prompt(field_name, group_logic, display_unit):
    """產生 OpenAI 的提示"""
    return f"""
    你是一個可以產生 Tableau 計算式的助理。請根據以下需求，產生CASE WHEN的計算欄位邏輯：
    1. 欄位名稱：{field_name}
    2. 分組邏輯（依序）：{group_logic}
    3. 若值為 null，顯示「無購買」（前綴序號為 1.）
    4. 若數值 <0，顯示 "< 0" （前綴序號為 2.）
    5. 之後依照順序處理區間（如 0 ~ 0、1 ~ 6、7 ~ 13 ...），使用 "<= 上限" 標記。第一個數值區間從 0 開始。
    6. 最後一組為 ">= [最後一個數值]" 格式。
    7. 每個分組顯示格式時，請加上前綴序號，並盡可能加上單位，如 "1. 無購買"、"2. < 0 {display_unit}"、"3. = 0 {display_unit}"、"4. 1 ~ 6 {display_unit}"...
    8. 單位：{display_unit}（若為空則省略單位）
    9. 僅需要回傳最終的 Tableau CASE WHEN 計算式程式碼區塊，請勿包含任何其他的解釋或說明文字。
    """

def show(client: OpenAI):
    """顯示連續值分組工具的介面和邏輯"""
    st.markdown("### 設定分組條件")

    # 使用 columns 來優化版面配置
    col1, col2 = st.columns(2)

    with col1:
        field_name = st.text_input(
            "輸入欄位名稱",
            value="[註冊到購買]",
            help="輸入 Tableau 中要進行分組的欄位名稱，例如 `[Sales]` 或 `DATEDIFF('day', [Order Date], [Ship Date])`"
        )

    with col2:
        display_unit = st.text_input(
            "顯示單位",
            value="天",
            help="輸入分組後顯示的單位（可選）"
        )

    group_logic_input = st.text_input(
        "輸入分組邏輯",
        value="null, <0, 0, 6, 13, 29, 59, 89",
        help="請依序輸入分組的邊界值，用逗號分隔。格式：`null, <0, 數字1, 數字2, ...`。例如 `null, <0, 0, 6, 13, 29` 表示 `null`, `<0`, `=0`, `1-6`, `7-13`, `>=14`"
    )

    # 驗證輸入
    is_valid, error_message = validate_group_logic(group_logic_input)
    if not is_valid:
        st.warning(f"分組邏輯格式錯誤：{error_message}")
        st.stop() # 如果格式錯誤，停止執行後續步驟

    st.markdown("---")

    if st.button("🚀 產生 Tableau 計算式", type="primary"):
        with st.spinner("🧠 AI 正在思考中..."):
            try:
                prompt = generate_prompt(field_name, group_logic_input, display_unit)

                response = client.chat.completions.create(
                    model="gpt-4o-mini", # 或其他適合的模型
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2 # 稍微降低 temperature 讓格式更穩定
                )
                formula = response.choices[0].message.content.strip()

                # 嘗試移除 Markdown 的程式碼區塊標記
                formula = formula.replace("```tableau", "").replace("```sql", "").replace("```", "").strip()

                st.success("✨ 計算式已生成！")
                st.code(formula, language="sql") # Tableau 語法高亮通常用 sql

                # 複製按鈕 (使用 streamlit-copy-button)
                # 需要先安裝 pip install streamlit-copy-button
                # from streamlit_copy_button import copy_button
                # copy_button(formula, "📋 複製計算式")
                # 備註：原生的 clipboard 可能在 Streamlit Cloud 有限制，建議用套件

            except AuthenticationError:
                st.error("OpenAI API 驗證失敗！請確認您的 API Key 是否正確且有效。")
            except RateLimitError:
                st.error("已達到 OpenAI API 使用限制，請稍後再試。")
            except Exception as e:
                st.error(f"生成計算式時發生預期外的錯誤：{str(e)}")
                st.exception(e) # 顯示詳細錯誤 traceback
