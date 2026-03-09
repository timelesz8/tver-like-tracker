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

# 2. ブラウザ設定（ロボットとバレないように）
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/122.0.0.0")
driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. データ取得とループ処理
rows = url_sheet.get_all_records()
print(f"全取得行数: {len(rows)}")

for row in rows:
    # ヘッダー名が「active」の場合の判定
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("series_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(10) # ページ読み込みをじっくり待つ

    try:
        # お気に入り数の要素を探す
        fav_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り登録')]/following-sibling::span")
        fav_text = fav_elem.text
        
        # 数値抽出
        numbers = re.findall(r'[\d.,万]+', fav_text)
        if numbers:
            val = numbers[0]
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            # スプレッドシートへ書き込み
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # 失敗したら active を FALSE にする (E列がactiveと仮定)
        cell = url_sheet.find(series_id)
        if cell:
            url_sheet.update_cell(cell.row, 5, "FALSE")
            print("ステータスを FALSE に更新しました")

driver.quit()
print("すべての処理が完了しました")
