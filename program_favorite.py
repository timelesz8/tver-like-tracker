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
    # active列(E列)がTRUEの行のみ実行
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    
    # URLが空の場合はスキップし、FALSEには書き換えない
    if not url:
        print(f"スキップ: {series_id} (URLが空です)")
        continue

    print(f"--- 処理開始: {series_id} ---")
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        
        # リダイレクト検知
        if "tver.jp/series/" not in driver.current_url:
             raise Exception(f"リダイレクトされました: {driver.current_url}")

        # お気に入り数要素の取得
        fav_container = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'お気に入り')]")))
        full_text = fav_container.find_element(By.XPATH, "..").text
        
        # 数値抽出
        numbers = re.findall(r'[\d\.]+[万]?', full_text)
        if numbers:
            val = numbers[0]
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} = {fav_count} (時刻: {now})")
        else:
            raise Exception(f"数値が見つかりませんでした。テキスト: {full_text}")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # URLがあるのに取得失敗した場合のみFALSEに更新（空行は更新しない）
        program_sheet.update_cell(idx + 2, 5, "FALSE")

driver.quit()
