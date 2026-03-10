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

# 2. ブラウザ設定 (update_script.py と同じ設定に統一)
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = program_sheet.get_all_records(head=1)

for idx, row in enumerate(rows):
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(5) 

    try:
        # リダイレクト検知を強化
        if "tver.jp/" not in driver.current_url or "home" in driver.current_url:
             raise Exception("トップページへリダイレクトされました")

        # 番組ページのお気に入り数取得 (TVer構造に対応)
        # 画面の表示(18.6万)を捉えるため、テキスト要素を直接検索
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'お気に入り')]")
        
        fav_count = None
        for el in elements:
            # 「お気に入り」という文字が含まれるタグを探し、数値を抽出
            numbers = re.findall(r'[\d\.]+[万]?', el.text)
            if numbers:
                fav_count = int(float(numbers[0].replace("万", "")) * 10000) if "万" in numbers[0] else int(numbers[0].replace(",", ""))
                break
        
        if fav_count is not None:
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} = {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # E列(5列目)をFALSEに更新
        program_sheet.update_cell(idx + 2, 5, "FALSE")

driver.quit()
