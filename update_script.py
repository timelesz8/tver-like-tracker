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
url_sheet = spreadsheet.worksheet("url_list")
like_sheet = spreadsheet.worksheet("like_data")

# 2. ブラウザ設定 (Actions用)
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

# 3. メイン処理
rows = url_sheet.get_all_records()

for row in rows:
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue

    episode_id = url.split("/")[-1]
    driver.get(url)
    time.sleep(2)  # テスト用に短縮した待機時間

    try:
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

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    like_sheet.append_row([now, episode_id, like])

driver.quit()
