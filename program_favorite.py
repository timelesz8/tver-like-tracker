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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 1. 設定
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
prog_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = prog_sheet.get_all_records()

for idx, row in enumerate(rows):
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    # 少し余裕を持つ
    time.sleep(8) 

    try:
        # 「お気に入り登録」というテキストを持つ要素を探す
        # その要素が含まれる親階層全体から、数値を探すアプローチ
        # 画面上の「18.6万」をピンポイントで狙うロジックです
        target_text = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り登録')]").find_element(By.XPATH, "..").text
        
        # 正規表現で「18.6万」のような数値を抽出
        match = re.search(r'([\d\.]+[万]?)', target_text)
        
        if match:
            val = match.group(1)
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} = {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"エラー発生: {series_id}, {e}")

driver.quit()
