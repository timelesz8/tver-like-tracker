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
os.environ['TZ'] = 'Asia/Tokyo'
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

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. メイン処理
rows = program_sheet.get_all_records(head=1)

for idx, row in enumerate(rows):
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url:
        continue

    print(f"--- 処理開始: {series_id} ---")
    
    try:
        driver.get(url)
        # 数値のレンダリングを待つ時間を確保
        time.sleep(10) 

        if "tver.jp/series/" not in driver.current_url:
             raise Exception(f"リダイレクトされました: {driver.current_url}")

        # 修正: ボタン全体を囲む要素を探す（class名が不明なため、より広い範囲の要素を取得）
        # 「お気に入り」を含むボタンやその親要素をすべて取得してテキストを結合
        wait = WebDriverWait(driver, 10)
        fav_buttons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//*[contains(text(), 'お気に入り')]")))
        
        full_text = ""
        for btn in fav_buttons:
            full_text += btn.text + " "

        # 数値抽出（「3.5万」のような形式）
        numbers = re.findall(r'[\d\.]+[万]?', full_text)
        
        if numbers:
            val = numbers[-1] # 最後に出た数値が最新のものと仮定
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} = {fav_count} (時刻: {now})")
        else:
            raise Exception(f"数値が見つかりませんでした。取得テキスト: {full_text}")

driver.quit()
