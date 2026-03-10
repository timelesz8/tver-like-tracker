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

# 3. メイン処理
rows = program_sheet.get_all_records()

for idx, row in enumerate(rows):
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    if not url: continue
    program_id = url.split("/")[-1]
    
    try:
        driver.get(url)
        # コンテンツの描画を待つ
        time.sleep(5)
        
        # お気に入りボタンが含まれる要素を特定
        # 画面上の「お気に入り登録」などのラベルを持つ要素を探す
        wait = WebDriverWait(driver, 15)
        elem = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@aria-label, 'お気に入り')]")))
        
        # episode_like.py と同様に親要素経由でテキストを取得して正規化
        parent = elem.find_element(By.XPATH, "..")
        text = parent.text
        
        # 数値抽出（例: 3.5万 -> 35000）
        numbers = re.findall(r'[\d.,万]+', text)
        if not numbers:
            raise Exception("数値が見つかりませんでした")
            
        fav_val = numbers[0].replace(",", "")
        count = int(float(fav_val.replace("万", "")) * 10000) if "万" in fav_val else int(fav_val)
        
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        fav_sheet.append_row([now, program_id, count])
        print(f"取得成功: {program_id} = {count}")
        
    except Exception as e:
        # デバッグ用にスクリーンショットを保存
        driver.save_screenshot(f"error_{program_id}.png")
        print(f"エラー発生: {program_id}, {e}")

driver.quit()
