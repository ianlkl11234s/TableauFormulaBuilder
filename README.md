# Tableau 計算欄位生成工具

這是一個使用 Streamlit 開發的工具，可以幫助使用者快速生成 Tableau 的計算欄位。

## 功能

- **連續值分組**: 自動生成 CASE WHEN 語法進行數值分組
- **是否標籤**: 快速生成 IIF 語法進行二元標記
- **訂單組合標記**: 生成多欄位組合的條件判斷
- **日期區間篩選**: 生成判斷日期是否在特定時間範圍內的公式
- **有無判斷**: 生成「有/無」格式的條件判斷

## 安裝與設定

1. 複製專案
```bash
git clone https://github.com/您的GitHub帳號/專案名稱.git
cd 專案名稱
```

2. 安裝相依套件
```bash
pip install -r requirements.txt
```

3. 設定環境變數
建立 `.env` 檔案並設定以下變數：
```plaintext
OPENAI_API_KEY=您的OpenAI_API_Key
GEMINI_API_KEY=您的Gemini_API_Key
ANTHROPIC_API_KEY=您的Claude_API_Key
```

4. 執行應用程式
```bash
streamlit run main.py
```

## 使用說明

1. 在側邊欄選擇要使用的 LLM 服務（OpenAI/Gemini/Claude）
2. 選擇要使用的工具（連續值分組/是否標籤）
3. 依照畫面提示輸入必要資訊
4. 點擊生成按鈕即可獲得 Tableau 計算欄位程式碼

## 授權

MIT License