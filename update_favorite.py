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

# 認証とシートの準備
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')

# 認証情報の読み込みを確認
print(f"シートID確認: {spreadsheet_id}")
# 認証が失敗していればここでエラーが出て止まるはずです

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
url_sheet = spreadsheet.worksheet("program_master")
fav_sheet = spreadsheet.worksheet("favorite_data")

# ロボットとバレないための設定（User-Agent偽装と自動操作フラグ隠蔽）
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

rows = url_sheet.get_all_records()

for row in rows:
    rows = url_sheet.get_all_records()
    print(f"読み込んだ行数: {len(rows)}") # 追加
for row in rows:
    print(f"現在処理中の行データ: {row}") # 追加
    # 日本語ヘッダー「実行フラグ」に対応
    if str(row.get("実行フラグ", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    series_id = row.get("番組ID", "")
    if not url: continue

    print(f"アクセス中: {url}")
    driver.get(url)
    time.sleep(8) # ページ読み込みを待つ

    try:
        # 「お気に入り登録」の文字列を含む要素から数値を抽出
        # 構造：お気に入り登録ボタンの近くの数値を取得
        fav_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り登録')]/following-sibling::span")
        fav_text = fav_elem.text
        
        # 数値抽出（万単位対応）
        numbers = re.findall(r'[\d.,万]+', fav_text)
        if numbers:
            val = numbers[0]
            fav_count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val.replace(",", ""))
            
            # スプレッドシートへ書き込み
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            fav_sheet.append_row([now, series_id, fav_count])
            print(f"取得成功: {series_id} -> {fav_count}")
        else:
            raise Exception("数値が見つかりませんでした")

    except Exception as e:
        print(f"取得失敗 ({series_id}): {e}")
        # エラー時は該当行の「実行フラグ」をFALSEに変更
        cell = url_sheet.find(series_id)
        if cell:
            # 5列目（E列）が実行フラグと仮定
            url_sheet.update_cell(cell.row, 5, "FALSE")
            print(f"ステータスを FALSE に更新しました")

driver.quit()
