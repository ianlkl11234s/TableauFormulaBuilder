import streamlit as st
from dotenv import load_dotenv
import os
from openai import OpenAI

# 載入不同工具的模組
from tools import continuous_binning, boolean_tagging

# 載入環境變數
load_dotenv()

# 設置 OpenAI 客戶端 (如果工具需要的話)
# 也可以考慮將 client 傳遞給需要的工具模組
api_key = os.getenv("OPENAI_API_KEY")
client = None
if api_key:
    client = OpenAI(api_key=api_key)
else:
    st.warning("找不到 OpenAI API Key！部分 AI 功能可能無法使用。請檢查 .env 檔案。")

# --- 側邊欄 ---
st.sidebar.title("🛠️ Tableau 小工具箱")
tool_options = {
    "連續值分組": continuous_binning.show,
    "是否標籤": boolean_tagging.show,
    # 未來可以繼續增加工具...
    # "日期格式轉換": date_formatter.show,
}
selected_tool = st.sidebar.radio("選擇工具：", list(tool_options.keys()))

# --- 主畫面 ---
st.title(f"📊 {selected_tool}")

# 執行選擇的工具函數，並傳遞 client (如果需要)
# 根據工具的需求，決定是否需要傳遞 client
if selected_tool == "連續值分組":
    if client:
        tool_options[selected_tool](client)
    else:
        st.error("此工具需要 OpenAI API Key，請先設置。")
elif selected_tool == "是否標籤":
     tool_options[selected_tool]() # 這個工具可能不需要 client
else:
     # 對於其他不需要 client 的工具
     tool_options[selected_tool]()

# --- 可以在這裡加入通用的頁尾資訊 ---
st.sidebar.info("由 AI 驅動的 Tableau 輔助工具")
