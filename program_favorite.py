import os
import json
import gspread
import time
import re
import requests  # 追加
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
gas_web_app_url = os.environ.get("GAS_WEB_APP_URL") # 環境変数に追加してください
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
        time.sleep(5)
        
        wait = WebDriverWait(driver, 15)
        # クラス名前方一致で要素取得
        elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class^='FavoriteButton_count']")))
        text = elem.text
        
        # 数値抽出（例: 3.5万 -> 35000）
        numbers = re.findall(r'[\d.,万]+', text)
        if not numbers:
            raise Exception("数値が見つかりませんでした")
            
        fav_val = numbers[0].replace(",", "")
        count = int(float(fav_val.replace("万", "")) * 10000) if "万" in fav_val else int(fav_val)
        
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        # 列の順番をBigQueryのスキーマ(observed_at, program_id, favorite_count)に合わせる
        fav_sheet.append_row([now, program_id, count])
        print(f"取得成功: {program_id} = {count}")
        
    except Exception as e:
        driver.save_screenshot(f"error_{program_id}.png")
        print(f"エラー発生: {program_id}, {e}")

driver.quit()

# 4. GASへBigQuery転送の通知を送る (追加)
if gas_web_app_url:
    try:
        # doPost または doGet に合わせてリクエストを送る
        response = requests.post(gas_web_app_url, json={"action": "export_all"})
        print(f"GAS通知完了: {response.status_code}")
    except Exception as e:
        print(f"GAS通知エラー: {e}")
