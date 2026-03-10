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

# 1. 設定と認証
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)

# 最新の構成に合わせる
prog_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = prog_sheet.get_all_records()

for idx, row in enumerate(rows):
    # O列(15列目)がactiveかどうか
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url: continue

    row_number = idx + 2
    
    try:
        driver.get(url)
        time.sleep(5) # ご指定の5秒に設定
        
        # 番組ページ特有の構造を探す（CSSセレクタで「お気に入り」テキストを含む要素を特定）
        # シリーズページでは「お気に入り」という文字が含まれるタグを探すのが最も確実です
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'お気に入り')]")
        
        found_val = None
        for el in elements:
            text = el.text
            if text and any(char.isdigit() for char in text):
                # 数値を抽出
                numbers = re.findall(r'[\d.,万]+', text)
                if numbers:
                    found_val = numbers[0]
                    break
        
        if not found_val:
            raise Exception("お気に入り数値が見つかりませんでした")
            
        fav_count = int(float(found_val.replace("万", "")) * 10000) if "万" in found_val else int(found_val.replace(",", ""))
        
        # 記録
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        fav_sheet.append_row([now, series_id, fav_count])
        print(f"取得成功: {series_id} = {fav_count}")

    except Exception as e:
        print(f"エラー発生: {series_id}, {e}")
        # 失敗時はO列をFALSEに
        prog_sheet.update_cell(row_number, 15, "FALSE")

driver.quit()
