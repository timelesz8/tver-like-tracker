import os
import json
import gspread
import re
import time
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 認証設定
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
# 提案通り、シート名を使い分けます
url_sheet = spreadsheet.worksheet("program_master") 
fav_sheet = spreadsheet.worksheet("favorite_data")

# ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

rows = url_sheet.get_all_records()

for row in rows:
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue

    series_id = url.split("/")[-1]
    driver.get(url)
    time.sleep(5) # 読み込み待機

    try:
        # 「お気に入り登録」というテキスト要素から数値を探す
        # 画面の構造上、お気に入り登録ボタンの近くにあるテキスト要素を取得します
        fav_element = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り登録')]/following-sibling::span")
        fav_text = fav_element.text
        
        # 数値抽出
        numbers = re.findall(r'[\d.,万]+', fav_text)
        if numbers:
            fav_raw = numbers[0]
            fav_count = int(float(fav_raw.replace("万", "")) * 10000) if "万" in fav_raw else int(fav_raw.replace(",", ""))
        else:
            fav_count = 0
            
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        fav_sheet.append_row([now, series_id, fav_count])
        
    except Exception as e:
        print(f"取得失敗 ({series_id}): {e}")

driver.quit()
