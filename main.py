import streamlit as st
from dotenv import load_dotenv
import os

# 載入 LLM 服務和工具模組
from tools.llm_services import get_llm_client, AVAILABLE_MODELS, LLMClientInterface
from tools import continuous_binning, boolean_tagging, order_combination, date_range, existence_check

# 載入環境變數
load_dotenv()

# --- 側邊欄 ---
st.sidebar.title("🛠️ Tableau 小工具箱")

# --- LLM 設定 ---
# 過濾掉沒有設定 API Key 的提供者
available_providers = []
if os.getenv("OPENAI_API_KEY"): available_providers.append("OpenAI")
if os.getenv("GEMINI_API_KEY"): available_providers.append("Gemini")
if os.getenv("ANTHROPIC_API_KEY"): available_providers.append("Claude")

if not available_providers:
    st.sidebar.warning("請在 .env 檔案中設定至少一個 LLM 的 API Key (例如 OPENAI_API_KEY)。")
    selected_provider = None
    llm_client = None
else:
    selected_provider = st.sidebar.selectbox(
        "選擇 LLM 提供者:",
        available_providers,
        index=0 # 預設選第一個可用的
    )
    # 根據選擇的提供者顯示可用模型
    if selected_provider:
        models_for_provider = AVAILABLE_MODELS.get(selected_provider.lower(), [])
        if models_for_provider:
            selected_model = st.sidebar.selectbox("選擇模型:", models_for_provider)
        else:
            st.sidebar.warning(f"找不到 {selected_provider} 的可用模型設定。")
            selected_model = None
        
        # 獲取 LLM 客戶端
        llm_client = get_llm_client(selected_provider)
        if not llm_client:
            st.sidebar.error(f"無法初始化 {selected_provider} 客戶端，請檢查 API Key 或網路連線。")

    else:
        llm_client = None
        selected_model = None

st.sidebar.markdown("---") # 分隔線

# --- 工具選擇 ---

# 定義工具及其是否需要 LLM
TOOLS_CONFIG = {
    "連續值分組": {
        "function": continuous_binning.show,
        "requires_llm": True
    },
    "是否標籤": {
        "function": boolean_tagging.show,
        "requires_llm": False
    },
    "訂單組合標記": {
        "function": order_combination.show,
        "requires_llm": True
    },
    "特定日期區間選擇": {
        "function": date_range.show,
        "requires_llm": False
    },
    "有無判斷": {
        "function": existence_check.show,
        "requires_llm": False
    }
}

selected_tool_name = st.sidebar.radio("選擇工具：", list(TOOLS_CONFIG.keys()))

# --- 主畫面 ---
st.title(f"📊 {selected_tool_name}")

# 獲取選擇的工具配置
tool_config = TOOLS_CONFIG[selected_tool_name]
selected_tool_func = tool_config["function"]
requires_llm = tool_config["requires_llm"]

# 根據工具需求執行對應的函數
if requires_llm:
    if llm_client and selected_model:
        # 將通用的 client 和選定的 model 傳遞給工具
        selected_tool_func(llm_client, selected_model)
    elif not selected_provider:
         st.error("請先在側邊欄設定有效的 LLM 提供者及 API Key。")
    elif not llm_client:
        st.error(f"無法載入 {selected_provider} 的 LLM 服務，請檢查側邊欄錯誤訊息。")
    else: # llm_client 有，但 selected_model 沒有
        st.error("請在側邊欄選擇一個模型。")
else:
    # 對於不需要 LLM 的工具，直接調用
    selected_tool_func()
