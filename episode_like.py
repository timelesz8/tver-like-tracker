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
url_sheet = spreadsheet.worksheet("episode_master")
like_sheet = spreadsheet.worksheet("like_data")

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = url_sheet.get_all_records()

for idx, row in enumerate(rows):
    # active列(O列)がTRUEの行のみ処理
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue

    episode_id = url.split("/")[-1]
    row_number = idx + 2  # ヘッダー分を考慮したスプレッドシート上の行番号
    
    try:
        driver.get(url)
        time.sleep(3)
        
        if "404" in driver.title or "ページが見つかりません" in driver.page_source:
            raise Exception("Page Not Found")

        elem = driver.find_element(By.XPATH, "//*[@aria-label='あとでみる']")
        parent = elem.find_element(By.XPATH, "..")
        numbers = re.findall(r'[\d.,万]+', parent.text)
        
        like = int(float(numbers[0].replace("万", "")) * 10000) if "万" in numbers[0] else int(numbers[0].replace(",", ""))
        
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        like_sheet.append_row([now, episode_id, like])
        print(f"取得成功: {episode_id} = {like}")

    except Exception as e:
        print(f"エラー発生: {episode_id}, {e}")
        # 列の移動に合わせて修正
        # active(O列) = 15列目, end_date(Q列) = 17列目, days_active(R列) = 18列目
        today = datetime.now(JST).strftime("%Y-%m-%d")
        url_sheet.update_cell(row_number, 15, "FALSE") # O列: active
        url_sheet.update_cell(row_number, 17, today)    # Q列: end_date
        # R列(days_active)はスプレッドシートの関数が自動計算するため更新不要
        print(f"ステータスを更新しました (行: {row_number})")

driver.quit()
