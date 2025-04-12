import streamlit as st
from .llm_services import LLMClientInterface # 引入通用介面

def validate_group_logic(logic_str):
    """驗證分組邏輯的格式"""
    try:
        values = [x.strip() for x in logic_str.split(",")]
        if not values: return False, "輸入不可為空"

        prev = -float('inf') # 允許第一個數字是 0 或負數
        for v in values[2:]:
            try:
                current = float(v)
                if current <= prev:
                    return False, f"數值必須依序嚴格遞增 (錯誤發生在: {prev} -> {current})"
                prev = current
            except ValueError:
                return False, f"'{v}' 不是有效的數字"
        return True, ""
    except Exception as e:
        return False, f"解析錯誤: {str(e)}"

def generate_prompt(field_name, group_logic, display_unit, has_null):
    """產生 OpenAI 的提示"""
    return f"""
        欄位名稱：
            {field_name}

            分組級距（依序）：
            {group_logic}

            值是否可能有 NULL 值：
            {'本欄位有 NULL 值，請記得要補上 IFNULL 的處理' if has_null else '本欄位無 NULL 值，不用特別考慮。'}


            顯示單位（可空白）：
            {display_unit}

            顯示格式需求：
            - 每個分組前請加上序號（例如 "1. ...", "2. ..."）({ '有 NULL，但 NULL 不要加序號，且請命名為無＿＿資料'if has_null else '' })
            - 分組區間請使用「起始 ~ 結束」的格式顯示（例：151 ~ 300）
            - 起始值請自動從上一個分組上限 +1 推算（第一組為最小值或特殊值）
            - 若有 <0、=0 等特殊條件，請獨立列出
            - 最後一組請使用「≥ 最大值」格式

        產出內容格式：

            - 請產生完整的 Tableau IF-ELSEIF 計算式
            - 每個條件請對應一段明確的區間說明與文字標籤
            - 若單位存在，請加在區間描述最後（例：400 ~ 600 元）
            - 若使用者未提供單位，則只顯示數字區間
            - 請在 ELSE 區段補上「其他」的處理（例如 '其他' 或 '未分類'）

        範例說明（請根據實際 breakpoints 判斷，不可照抄）：

            欄位：[客單價]
            分組：150, 300, 500, 1000, 2000
            顯示單位：元

            結果：
            ------
            IF [客單價] <= 150 THEN
                "1. ≤ 150 元"
            ELSEIF [客單價] <= 300 THEN
                "2. 151 ~ 300 元"
            ELSEIF [客單價] <= 500 THEN
                "3. 301 ~ 500 元"
            ELSEIF [客單價] <= 1000 THEN
                "4. 501 ~ 1000 元"
            ELSEIF [客單價] <= 2000 THEN
                "5. 1001 ~ 2000 元"
            ELSE
                "6. ≥ 2001 元"
            END
            ------

        請直接根據我提供的欄位與級距資料，產出上述格式的計算欄位語法。不需要額外說明，不要額外補充任何解釋。
    """

def show(llm_client: LLMClientInterface, model_name: str):
    """顯示連續值分組工具的介面和邏輯"""
    st.markdown("##### 設定分組條件")
    st.write("這個可以用來將欄位進行分組，尤其是像是客單價或是營收")

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

    # 值是否可能有 NULL 值
    has_null = st.checkbox(
        "值有 NULL 值",
        value=True,
        help="勾選此選項會考慮 NULL 值的情況"
    )

    # 驗證輸入
    is_valid, error_message = validate_group_logic(group_logic_input)
    if not is_valid:
        st.warning(f"分組邏輯格式錯誤：{error_message}")
        st.stop() # 如果格式錯誤，停止執行後續步驟

    st.markdown("---")

    if st.button("🚀 產生 分組計算式", type="primary"):
        with st.spinner(f"🧠 使用 {model_name} 思考中..."):
            try:
                prompt = generate_prompt(field_name, group_logic_input, display_unit, has_null)

                # 使用傳入的 client 和 model_name 呼叫通用方法
                formula = llm_client.generate_text(
                    prompt=prompt,
                    model=model_name,
                    temperature=0.2
                )

                # 嘗試移除 Markdown 的程式碼區塊標記
                formula = formula.replace("```tableau", "").replace("```sql", "").replace("```", "").strip()

                st.success("✨ 計算式已生成！")
                st.code(formula, language="sql") # Tableau 語法通常用 sql


            except ConnectionError as e: # Client 未初始化
                st.error(f"LLM 客戶端連線錯誤: {e}")
            except ConnectionAbortedError as e: # OpenAI Key 錯誤
                st.error(f"API 金鑰驗證失敗: {e}")
            except ConnectionRefusedError as e: # Rate Limit
                st.error(f"API 速率限制: {e}")
            except RuntimeError as e: # API 返回錯誤或未知錯誤
                st.error(f"LLM API 呼叫失敗: {e}")
            except Exception as e: # 其他未知錯誤
                st.error(f"生成計算式時發生預期外的錯誤：{str(e)}")
                st.exception(e) # 顯示詳細錯誤 traceback
