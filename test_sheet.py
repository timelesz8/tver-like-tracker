import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import datetime
import re

# ======================
# Google Sheets 接続
# ======================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=scope
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_key("1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8")

url_sheet = spreadsheet.worksheet("url_list")
like_sheet = spreadsheet.worksheet("like_data")

print("Sheets接続OK")

# ======================
# URL取得
# ======================

rows = url_sheet.get_all_records()

print("rows:", rows)
print("行数:", len(rows))

driver = webdriver.Chrome()

for row in rows:

    print("row:", row)

    # active 判定（文字列にも対応）
    if str(row.get("active", "")).upper() != "TRUE":
        print("skip inactive")
        continue

    url = row.get("url", "")

    if url == "":
        print("URLなし")
        continue

    # episode_id 抽出
    episode_id = url.split("/")[-1]

    print("取得中:", episode_id)

    driver.get(url)

    time.sleep(6)

    try:
        elem = driver.find_element(By.XPATH, "//*[@aria-label='あとでみる']")
        parent = elem.find_element(By.XPATH, "..")

        text = parent.text

        numbers = re.findall(r'[\d.,万]+', text)

        like_raw = numbers[0]

        # 万表記を変換
        if "万" in like_raw:
            like = int(float(like_raw.replace("万", "")) * 10000)
        else:
            like = int(like_raw.replace(",", ""))

    except Exception as e:
        print("like取得失敗:", e)
        like = 0

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("書き込み:", now, episode_id, like)

    like_sheet.append_row([now, episode_id, like])

    print("like:", like)

driver.quit()

print("完了")