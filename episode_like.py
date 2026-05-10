import os
import json
import time
import re
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# 1. 設定と認証
# =========================

service_account_info = json.loads(os.environ["GCP_SA_KEY"])
SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)

# =========================
# シート接続
# =========================

spreadsheet = client.open_by_key(SPREADSHEET_ID)
# エピソードいいね用のマスタシート（もし別名なら書き換えてください）
program_sheet = spreadsheet.worksheet("program_master")

try:
    like_sheet = spreadsheet.worksheet("episode_like_data")
except:
    print("episode_like_data シートが無いので作成します")
    like_sheet = spreadsheet.add_worksheet(title="episode_like_data", rows="1000", cols="10")
    like_sheet.append_row(["datetime", "program_id", "like_count"])

print("シート接続OK")

# =========================
# 2. ブラウザ設定
# =========================

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

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
        print(f"処理開始: {program_id}")
        driver.get(url)

        # 読み込み待機
        time.sleep(5)
        wait = WebDriverWait(driver, 15)

        # 「いいね」ボタンの要素を特定（TVerの仕様に合わせたクラス名）
        # ※クラス名は時期により変わる可能性があるため、前方一致で取得
        # 「aria-labelに 'いいね' を含むボタン」の中にある「IconButton_labelで始まるクラス」を指定
        elem = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button[aria-label*='いいね'] [class^='IconButton_label']")
            )
        )

        text = elem.text
        
        # 数値抽出（3.5万 -> 35000）
        numbers = re.findall(r'[\d.,万]+', text)
        if not numbers:
            raise Exception("いいね数が見つかりませんでした")

        val = numbers[0].replace(",", "")
        if "万" in val:
            count = int(float(val.replace("万", "")) * 10000)
        else:
            count = int(val)

        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        
        # 書き込み
        like_sheet.append_row([now, program_id, count])
        print(f"取得成功: {program_id} = {count}")

    except Exception as e:
        driver.save_screenshot(f"error_like_{program_id}.png")
        print(f"エラー発生: {program_id}, {e}")

driver.quit()
print("全処理終了")
