import os
import json
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# 1. 認証設定 (GitHub Secretsから取得)
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]

# 【ここを修正しました】
# スコープを明示的に指定して、サービスアカウントの情報を読み込みます
creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(spreadsheet_id)
like_sheet = spreadsheet.worksheet("like_data")

# 2. ブラウザ設定
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(options=chrome_options)

# 3. 指定のURLにアクセス
target_url = "https://tver.jp/episodes/epl2lol2f0"
driver.get(target_url)
time.sleep(10) # 念のため長めに待機

# 4. 要素を取得してA66に書き込み
try:
    # ページ内に「あとでみる」があるか確認（find_elementsで複数取得してみる）
    elems = driver.find_elements(By.XPATH, "//*[@aria-label='あとでみる']")
    
    print(f"見つかった要素の数: {len(elems)}")
    
    if len(elems) > 0:
        parent = elems[0].find_element(By.XPATH, "..")
        print(f"発見したテキスト全体: '{parent.text}'")
        
        # C66に値を入れるテスト
        like_sheet.update_acell('C66', parent.text)
        print("書き込み完了")
    else:
        print("警告: 要素が見つかりませんでした")
        # ページ全体のHTMLを確認用に出力
        print("--- HTMLの冒頭 ---")
        print(driver.page_source[:1000])
        print("--- HTMLの末尾 ---")
        print(driver.page_source[-1000:])
except Exception as e:
    print(f"エラー発生: {e}")
    # ページの一部を出力して確認
    print(driver.page_source[:500])

driver.quit()
