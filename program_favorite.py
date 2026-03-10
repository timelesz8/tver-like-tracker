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

# 1. 設定
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
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. データ取得
# ヘッダー行を明示的に指定して重複エラーを回避
rows = program_sheet.get_all_records(head=1)

for idx, row in enumerate(rows):
    # E列(active)がTRUEか判定
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組_id", "")
    if not url: continue

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(5) 

    try:
        # ページ全体のテキストからリダイレクト検知
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "ログイン" in body_text[:100] and "マイページ" in body_text[:100]:
             raise Exception("トップページにリダイレクトされました")

        # 「お気に入り登録」の隣の数値を探すロジック
        # 画面の表示構造に基づき、テキストノードを検索
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'お気に入り登録')]")
        
        fav_count = None
        for el in elements:
            # ボタンの親要素のテキストを取得
            parent_text = el.find_element(By.XPATH, "..").text
            match = re.search(r'([\d\.]+[万]?)', parent_text.replace("お気に入り登録", "").strip())
            if match:
                val = match.group(1)
                fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
                break
        
        if fav_count is not None:
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"成功: {series_id} = {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # E列(5列目)をFALSEに更新
        row_number = idx + 2
        program_sheet.update_cell(row_number, 5, "FALSE")

driver.quit()
