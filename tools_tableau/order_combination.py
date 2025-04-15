import streamlit as st
from core.llm_services import LLMClientInterface

def generate_prompt(field_names, handle_null=True, prefix="", suffix="", has_negative=True, is_value=True, is_yn=False):
    """生成給 LLM 的提示"""
    fields_str = "\n".join(f"- {name}" for name in field_names)
    
    prompt = f"""
    你是一個熟捻 Tableau 計算式的資料分析師。請根據以下需求，產生 IF ELSE ELSEIF 的計算欄位邏輯：

    欄位清單：
    {fields_str}

    目的：
    - 我會提供給你一系列的欄位，這些欄位都代表了餐廳是否有某個特徵標籤，像是是否有 A 標籤，是否有 B 標籤，是否兩者都有，或是兩者都無
    - 不一定只有 2 x 2 的組合，有可能會有更多，會需要請你幫我判斷，並且產生相對應的計算式

    需求與判斷邏輯說明：
    1. 使用 IF ELSE ELSEIF 產生一個計算欄位，判斷不同欄位組合的情況
    2. {'本欄位只判斷是否有值，也就是 ISNULL / NOT ISNULL 的判斷方式，不會出現數字比較' if is_value else '本欄位只有正數，因此只要判斷是否大於等於零就好'}
    3. {'本欄位有 NULL 值，因此「>0」,（沒有該標籤的值，有可能是「=0」也有可能是 NULL)' if handle_null else '本欄位無 NULL 值，只需要「>0」,「=0」來組合即可。'}
    4. {'本欄位有負值，請記得要處理負值的狀態，要出現「>0」、「<0」、「=0」的條件判斷' if has_negative else ''}
    5. {'本欄位只會出現 Y 和 N，Y 代表有，N 代表無，要出現「Y」、「N」的條件判斷' if is_yn else ''}


    結果標籤格式：
    - 對於單一欄位 > 0："{prefix}只有欄位名稱{suffix}"
    - 對於多個欄位 > 0："{prefix}只有欄位1/欄位2{suffix}"
    - 若是全有或是全無，請依據欄位的名稱來判斷相關命名

    顯示名稱處理：
    - 保留核心的業務含義，注意大部分的判斷都是是否有此功能，或是是否有使用哪一些服務的分類

    請生成完整的 Tableau 計算欄位程式碼，包含適當的註解說明。
    只需要回傳最終的計算式，不需要其他解釋。
    並請依據欄位的意義，給予一個簡短的欄位名稱。

    【範例一】（請注意為範例，不要照抄，要依據內容判斷：
    欄位：[區間內_外帶外送訂單數], [區間內_內掃訂單數]
    計算式：
    ------
    IF 
    [區間內_外帶外送訂單數]>0 AND
    [區間內_內掃訂單數]>0 THEN '外帶外送_內掃都有'

    ELSEIF 
    [區間內_外帶外送訂單數]>0 AND
    ISNULL([區間內_內掃訂單數]) THEN '只有外帶外送'

    ELSEIF 
    ISNULL([區間內_外帶外送訂單數]) AND
    [區間內_內掃訂單數]>0 THEN '只有內掃'

    ELSEIF 
    ISNULL([區間內_外帶外送訂單數]) AND
    ISNULL([區間內_內掃訂單數]) THEN '皆無'

    ELSE 'other'
    END
    ------

    【範例二】（請注意為範例，不要照抄，要依據內容判斷：
    欄位：[區間內FP訂單數], [區間內GF訂單數]
    計算式：
    ------
    IF 
    [區間內FP訂單數] AND
    [區間內GF訂單數]>0 THEN 'FP/GF都有'

    ELSEIF 
    [區間內FP訂單數]>0 AND
    ISNULL([區間內GF訂單數]) THEN '只有FP'

    ELSEIF 
    ISNULL([區間內FP訂單數]) AND
    [區間內GF訂單數]>0 THEN '只有GF'

    ELSEIF 
    ISNULL([區間內FP訂單數]) AND
    ISNULL([區間內GF訂單數]) THEN '皆無'

    ELSE 'other'
    END
    ------

    【範例三】（請注意為範例，不要照抄，要依據內容判斷：
    欄位：[是否有點餐模組], [是否有外送模組]
    計算式：
    ------
    IF 
    [是否有點餐模組] = 'Y' AND
    [是否有外送模組] = 'Y' THEN '點餐模組_外送模組都有'

    ELSEIF 
    [是否有點餐模組] = 'Y' AND
    [是否有外送模組] = 'N' THEN '只有點餐模組'

    ELSEIF 
    [是否有點餐模組] = 'N' AND
    [是否有外送模組] = 'Y' THEN '只有外送模組'

    ELSEIF 
    [是否有點餐模組] = 'N' AND
    [是否有外送模組] = 'N' THEN '皆無'

    ELSE 'other'
    END
    ------
    """
    return prompt

def show(llm_client: LLMClientInterface, model_name: str):
    """顯示訂單組合標記工具的介面和邏輯"""
    st.markdown("##### 訂單組合標記")
    st.write("""
    這個工具可以幫助您生成多個欄位的組合條件判斷，適合用於分析不同類型訂單的組合情況。
    使用 AI 協助生成更靈活的判斷邏輯。
    """)

    # 輸入欄位
    field_names_input = st.text_area(
        "輸入欄位名稱（每行一個）",
        value="[區間內FP訂單數]\n[區間內GF訂單數]",
        height=150,
        help="每行輸入一個欄位名稱，可以直接從 Tableau 複製欄位名稱。"
    )

    # 設定區域
    st.markdown("---")
    st.markdown("##### 進階設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # NULL 值處理選項
        handle_null = st.checkbox(
            "處理 NULL 值",
            value=False,
            help="""
            勾選此選項會：
            1. 將「全部欄位皆為 NULL」作為獨立情況處理
            2. 在判斷時明確處理 NULL 值（使用 IS NULL/IS NOT NULL）
            不勾選則使用簡單的數值比較。
            """
        )

    with col2:
        # 是否會有負值
        has_negative = st.checkbox(
            "是否會有負值", 
            value=False,
            help="""
            勾選此選項會：
            1. 將「可能包含負值」作為獨立情況處理
            2. 在判斷時明確處理負值（使用 < 0）
            不勾選則使用簡單的數值比較。
            """
        )

    col1, col2 = st.columns(2)
    with col1:
        # 判斷依據是否有值
        is_value = st.checkbox(
            "判斷依據是否有值",
            value=False,
            help="""
            勾選此選項會：
            將「只判斷是否有值」
            不勾選則使用簡單的數值比較。
            """
        )
    with col2:
        # 是否為 Y/N 的判斷
        is_yn = st.checkbox(
            "是否為 Y/N 的判斷",
            value=False,
            help="""
            勾選此選項會：
            只會出現 Y 和 N 的判斷，不會出現其他值
            """ 
        )    


    # 前綴後綴設定
    col1, col2 = st.columns(2)
    with col1:
        prefix = st.text_input(
            "結果前綴",
            value="",
            help="可選：在結果前加上文字"
        )
    with col2:
        suffix = st.text_input(
            "結果後綴",
            value="",
            help="可選：在結果後加上文字"
        )

    if st.button("🔄 產生組合條件", type="primary"):
        # 處理輸入
        field_names = [name.strip() for name in field_names_input.split('\n') if name.strip()]

        if len(field_names) < 2:
            st.warning("請至少輸入兩個欄位名稱。")
            st.stop()

        # 生成提示並呼叫 LLM
        with st.spinner(f"🧠 使用 {model_name} 思考中..."):
            try:
                prompt = generate_prompt(field_names, handle_null, prefix, suffix, has_negative, is_value, is_yn)
                
                # 使用 LLM 生成結果
                formula = llm_client.generate_text(
                    prompt=prompt,
                    model=model_name,
                    temperature=0.2
                )

                # 清理結果（移除可能的 Markdown 標記）
                formula = formula.replace("```tableau", "").replace("```sql", "").replace("```", "").strip()

                st.success("✨ 計算式已生成！")
                st.code(formula, language="sql")

            except Exception as e:
                st.error(f"生成計算式時發生錯誤：{str(e)}")
                st.exception(e)