# 這裡負責生成要探索 table 的 SQL 語法
"""""
目前會想要包含以下內容：
- 填入 table 名稱
- 放上想要特別 group by 確認的欄位，自動產生語法（或是用勾選的）
- 查看特定 id 或是查看特定店家的資料

"""""

# 探索 table 的 SQL 語法
sql_query = """
SELECT 
    field,
    count(*) AS total_count,
    COUNT(DISTINCT id) AS distinct_count
FROM 
GROUP BY 1
"""

# 執行 SQL 語法
