import os
import json
import gspread
import datetime
import re
import time
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. 認証設定 (GitHub Secretsから取得)
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)

spreadsheet = client.open_by_key(spreadsheet_id)
url_sheet = spreadsheet.worksheet("url_list")
like_sheet = spreadsheet.worksheet("like_data")

# 2. ブラウザ設定 (GitHub Actions用のヘッドレスモード)
chrome_options = Options()
chrome_options.add_argument("--headless=new") # 画面を出さずに実行
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = url_sheet.get_all_records()

for row in rows:
    # active列がTRUEのものだけ処理
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue

    episode_id = url.split("/")[-1]
    print(f"取得中: {episode_id}")
    
    driver.get(url)
    time.sleep(6) # ページ読み込み待ち

    try:
        # TVerの「あとでみる」ボタン付近から数値を抽出
        elem = driver.find_element(By.XPATH, "//*[@aria-label='あとでみる']")
        parent = elem.find_element(By.XPATH, "..")
        text = parent.text
        numbers = re.findall(r'[\d.,万]+', text)
        
        if numbers:
            like_raw = numbers[0]
            if "万" in like_raw:
                like = int(float(like_raw.replace("万", "")) * 10000)
            else:
                like = int(like_raw.replace(",", ""))
        else:
            like = 0
            
    except Exception as e:
        print(f"取得失敗: {episode_id}, {e}")
        like = 0

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    like_sheet.append_row([now, episode_id, like])
    print(f"書き込み完了: {episode_id}, {like}")

driver.quit()
