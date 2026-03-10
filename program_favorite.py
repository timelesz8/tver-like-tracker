import os
import json
import gspread
import time
import re
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# 1. 設定
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)

program_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# 2. ブラウザ設定（リダイレクト回避のため強力に設定）
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# ユーザーエージェントと言語設定を偽装
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
chrome_options.add_argument("--lang=ja-JP")

driver = webdriver.Chrome(options=chrome_options)
# ボット判定を回避するためのJS実行
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. データ取得
rows = program_sheet.get_all_records()

for row in rows:
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(5) 

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # リダイレクトチェック（トップページではないか）
        if "ログイン" in body_text[:100] and "マイページ" in body_text[:100]:
             # 念のためもう一度だけアクセスしてみる
             driver.get(url)
             time.sleep(5)
             body_text = driver.find_element(By.TAG_NAME, "body").text

        match = re.search(r'([\d\.]+[万]?)お気に入り', body_text)
        
        if match:
            val = match.group(1)
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count]) 
            print(f"成功: {series_id} = {fav_count}")
        else:
            raise Exception("お気に入り数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")

driver.quit()
