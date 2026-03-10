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

# 1. 認証とシートの準備
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)

# シートの定義
episode_sheet = spreadsheet.worksheet("episode_master")
program_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# 2. マスターデータの読み込み (URLをキーにしてIDを引く辞書を作成)
program_rows = program_sheet.get_all_records()
# program_masterのA列(id)とD列(url)を参照して辞書化
url_to_id_map = {row.get("url", ""): row.get("id", "") for row in program_rows}

# 3. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/122.0.0.0")
driver = webdriver.Chrome(options=chrome_options)

# 4. データ取得と保存
rows = episode_sheet.get_all_records()

for idx, row in enumerate(rows):
    # active列(O列)がTRUEの行のみ処理
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("url", "")
    if not url: continue
    
    # 辞書から番組IDを取得
    series_id = url_to_id_map.get(url, "ID不明") 

    print(f"--- 処理開始: {series_id} (URL: {url}) ---")
    driver.get(url)
    time.sleep(10) 

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        # 数値抽出の正規表現
        match = re.search(r'お気に入り登録\s*([\d\.]+[万]?)', body_text)
        
        if match:
            val = match.group(1)
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            # 書き込み
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count]) 
            print(f"成功: {series_id} = {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"失敗 ({series_id}): {e}")
        # O列(15列目)の active を FALSE に更新
        row_number = idx + 2
        episode_sheet.update_cell(row_number, 15, "FALSE")
        print("ステータスを FALSE に更新しました")

driver.quit()
print("すべての処理が完了しました")
