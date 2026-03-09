import os
import json
import gspread
import time
import re
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. 認証設定
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
url_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/122.0.0.0")
driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. データ取得
rows = url_sheet.get_all_records()
print(f"全取得行数: {len(rows)}")

for row in rows:
    # 修正：ヘッダー名 "active" を直接取得。大文字小文字を区別しないよう処理
    status = str(row.get("active", "")).upper()
    
    # 実行前に、なぜスキップされるかを確認するためのデバッグ出力
    print(f"ID: {row.get('series_id')}, ステータス: {status}")

    if status != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("series_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(10) 

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'お気に入り登録\s*([\d\.]+[万]?)', body_text)
        
        if match:
            val = match.group(1)
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} は {fav_count} でした")
        else:
            raise Exception("お気に入り登録の数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # ヘッダー名が「active」の列をE列(5列目)と指定して更新
        cell = url_sheet.find(series_id)
        if cell:
            url_sheet.update_cell(cell.row, 5, "FALSE")
            print("ステータスを FALSE に更新しました")

driver.quit()
print("すべての処理が完了しました")
