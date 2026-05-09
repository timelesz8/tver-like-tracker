import os
import json
import gspread
import re
import time
import requests  # GASへの通知用に追加
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. 設定と認証
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
# GASのウェブアプリURL（GitHubのSecretsに追加してください）
gas_webhook_url = os.environ.get("GAS_WEBAPP_URL")

JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
url_sheet = spreadsheet.worksheet("episode_master")
like_sheet = spreadsheet.worksheet("like_data")

# --- 重複防止チェック (30分ルール) ---
def is_already_fetched_this_hour(sheet):
    try:
        data = sheet.get_all_values()
        if len(data) < 2: return False
        last_time_str = data[-1][0]
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        now = datetime.now(JST)
        # 30分以内に記録があればスキップ
        if now - last_time < timedelta(minutes=30):
            return True
    except Exception as e:
        print(f"チェックエラー: {e}")
    return False

# GASからの強制トリガーの場合はスキップを無効にしたい場合はここを調整
if is_already_fetched_this_hour(like_sheet):
    print("直近30分以内に実行済みのためスキップします。")
    exit()

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
success_count = 0

for idx, row in enumerate(rows):
    # active列がTRUEの行のみ処理
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue

    episode_id = url.split("/")[-1]
    row_number = idx + 2  # ヘッダー分
    
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
        success_count += 1

    except Exception as e:
        print(f"エラー発生: {episode_id}, {e}")
        today = datetime.now(JST).strftime("%Y-%m-%d")
        url_sheet.update_cell(row_number, 14, "FALSE") # O列: active
        url_sheet.update_cell(row_number, 16, today)    # Q列: end_date
        print(f"ステータスを更新しました (行: {row_number})")

driver.quit()

# 4. GASへ完了通知（BigQuery転送のキック）
if success_count > 0 and gas_webhook_url:
    try:
        print("GASにBigQuery転送をリクエスト中...")
        response = requests.post(gas_webhook_url)
        print(f"GAS通知結果: {response.status_code}")
    except Exception as e:
        print(f"GAS通知エラー: {e}")
