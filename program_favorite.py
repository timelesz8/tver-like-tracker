import os
import json
import time
import re
from datetime import datetime, timedelta, timezone

# 以下のライブラリがGitHub Actions環境に必要です
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError as e:
    print(f"エラー: ライブラリが足りません。 {e}")
    print("requirements.txt に gspread, google-auth, selenium が含まれているか確認してください。")
    exit(1)

# =========================
# 1. 設定と認証
# =========================

# 環境変数から認証情報とシートIDを取得
try:
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]
except KeyError as e:
    print(f"エラー: 環境変数が設定されていません。 {e}")
    exit(1)

JST = timezone(timedelta(hours=+9), 'JST')

# Google APIのスコープ設定
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)

# =========================
# シート接続
# =========================

try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    program_sheet = spreadsheet.worksheet("program_master")
except Exception as e:
    print(f"エラー: スプレッドシートへのアクセスに失敗しました。 {e}")
    exit(1)

try:
    fav_sheet = spreadsheet.worksheet("favorite_data")
except Exception:
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
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)

# =========================
# 3. メイン処理
# =========================

rows = program_sheet.get_all_records()

for idx, row in enumerate(rows):
    # アクティブでない番組はスキップ
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    if not url:
        continue

    program_id = url.split("/")[-1]

    try:
        print(f"処理開始: {program_id}")
        driver.get(url)

        # コンテンツの描画を待つ
        time.sleep(5)

        # お気に入りボタンの数値が含まれる要素を待機
        wait = WebDriverWait(driver, 15)
        elem = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[class^='FavoriteButton_count']")
            )
        )

        text = elem.text
        
        # 数値抽出（例: 3.5万 -> 35000）
        numbers = re.findall(r'[\d.,万]+', text)
        if not numbers:
            raise Exception("数値が見つかりませんでした")

        fav_val = numbers[0].replace(",", "")
        
        if "万" in fav_val:
            count = int(float(fav_val.replace("万", "")) * 10000)
        else:
            count = int(fav_val)

        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        
        # スプレッドシートへ書き込み
        fav_sheet.append_row([now, program_id, count])
        print(f"取得成功: {program_id} = {count}")

    except Exception as e:
        # デバッグ用にスクリーンショットを保存
        driver.save_screenshot(f"error_{program_id}.png")
        print(f"エラー発生: {program_id}, {e}")

# ブラウザを閉じて終了
driver.quit()
print("全処理終了")
