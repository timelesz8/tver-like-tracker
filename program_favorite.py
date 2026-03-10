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

# (1. 設定部分はそのまま)
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
JST = timezone(timedelta(hours=+9), 'JST')
# ... (略) ...

# 2. ブラウザ設定を「より人間らしく」強化
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# 画面サイズを大きくする
chrome_options.add_argument("--window-size=1920,1080")
# User-Agent をより一般的なブラウザに偽装
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)

# Bot検知を回避するためのスクリプト実行
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# 3. メイン処理
# ... (略) ...

    print(f"--- 処理開始: {series_id} ---")
    driver.get(url)
    time.sleep(8) # 読み込み時間を5秒→8秒に少し延長

    try:
        # URLが変わっていないか、TVerの番組ページに留まっているか厳密にチェック
        if "tver.jp/series/" not in driver.current_url:
             raise Exception(f"リダイレクトされました: {driver.current_url}")

        # お気に入り数取得のロジック
        # 画面の構造上、「お気に入り登録」ボタンの周りのテキストを狙う
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'お気に入り')]")
        
        # ... (以下、正規表現での数値抽出部分はそのまま維持)
