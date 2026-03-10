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

# 1. 認証とシートの準備
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
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/122.0.0.0")
driver = webdriver.Chrome(options=chrome_options)

# 3. データ取得と保存
rows = program_sheet.get_all_records()

for idx, row in enumerate(rows):
    # active列がTRUEの行のみ処理
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    # ヘッダー名を「番組URL」に修正
    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "") # A列のヘッダー名を確認してください
    if not url: continue

    print(f"--- 処理開始: {series_id} (URL: {url}) ---")
    driver.get(url)
    time.sleep(10) 

    try:
        # シリーズページでは「お気に入り」というラベルを含むボタンのテキストを取得
        # ページ全体のテキストから数値を探すロジックに変更
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # 数値のパターンを少し広めに設定
        match = re.search(r'([\d\.]+[万]?)お気に入り', body_text)
        
        if match:
            val = match.group(1)
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count]) 
            print(f"成功: {series_id} = {fav_count}")
        else:
            # デバッグ用に取得したテキストの一部を表示
            print(f"数値が見つかりませんでした。ページテキストの一部: {body_text[:100]}")
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")

driver.quit()
print("すべての処理が完了しました")
