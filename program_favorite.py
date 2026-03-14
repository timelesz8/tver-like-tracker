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

# =========================
# 1. Google認証
# =========================

service_account_info = json.loads(os.environ["GCP_SA_KEY"])

SPREADSHEET_ID = "1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8"

JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_key(SPREADSHEET_ID)

# =========================
# シート取得
# =========================

program_sheet = spreadsheet.worksheet("program_master")

try:
    fav_sheet = spreadsheet.worksheet("favorite_data")
except:
    print("favorite_data シートが無いので作成します")
    fav_sheet = spreadsheet.add_worksheet(title="favorite_data", rows="1000", cols="10")
    fav_sheet.append_row(["datetime", "program_id", "favorite_count"])

print("シート接続OK")

# =========================
# 2. ブラウザ設定
# =========================

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=chrome_options)

# =========================
# 3. メイン処理
# =========================

rows = program_sheet.get_all_records()

for idx, row in enumerate(rows):

    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    if not url:
        continue

    program_id = url.split("/")[-1]

    try:

        driver.get(url)

        time.sleep(5)

        wait = WebDriverWait(driver, 15)

        elem = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[class^='FavoriteButton_count']")
            )
        )

        text = elem.text

        numbers = re.findall(r'[\d.,万]+', text)

        if not numbers:
            raise Exception("数値が見つかりません")

        fav_val = numbers[0].replace(",", "")

        if "万" in fav_val:
            count = int(float(fav_val.replace("万", "")) * 10000)
        else:
            count = int(fav_val)

        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

        print("書き込み:", now, program_id, count)

        fav_sheet.append_row([now, program_id, count])

        print("保存成功")

    except Exception as e:

        driver.save_screenshot(f"error_{program_id}.png")

        print("エラー:", program_id, e)

driver.quit()

print("処理終了")
