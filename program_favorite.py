import os
import json
import gspread
import re
import time
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

Gemini の回答
GitHub Actionsのログにある RefreshError は、ほとんどの場合、GitHub Secretsの文字列が正しく環境変数にロードされていないことが原因です。

YAMLを介さずに（つまり、Actionsの設定ファイルをいじらずに）コード側でこのエラーを回避・デバッグするための確実な手順をお伝えします。

1. 認証情報をファイルとして保存する
環境変数経由の読み込み (json.loads) は、改行コードのズレなどで失敗しやすいです。以下のコードのように、プログラムの中で一旦キーをファイルとして保存してから読み込む方法に書き換えてみてください。

Python
# 1. 設定と認証部分を以下のように修正
import os
import json

# GitHub Secretsの値を環境変数から取得
key_json_str = os.environ.get("GCP_SA_KEY")

# 一旦ファイルとして書き出す
with open("sa_key.json", "w") as f:
    f.write(key_json_str)

# ファイルから認証情報をロードする
creds = Credentials.from_service_account_file(
    "sa_key.json",
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
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

def parse_favorite_count(text):
    """ '3.5万' や '1,234' を数値に変換 """
    text = text.replace(",", "").replace("お気に入り済み", "").replace("お気に入り登録", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    return int(text)

# 3. メイン処理
rows = program_sheet.get_all_records()

for idx, row in enumerate(rows):
    if str(row.get("active", "")).upper() != "TRUE":
        continue

    url = row.get("番組URL", "")
    program_id = url.split("/")[-1]
    
    try:
        driver.get(url)
        # 人間っぽく少し待機
        time.sleep(5) 
        
        # 'お気に入り登録' または 'お気に入り済み' の両方に対応するXPath
        xpath_query = "//*[contains(@aria-label, 'お気に入り')]"
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath_query)))
        
        raw_text = element.get_attribute("aria-label")
        count = parse_favorite_count(raw_text)
        
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        fav_sheet.append_row([now, program_id, count])
        print(f"取得成功: {program_id} = {count}")
        
    except Exception as e:
        print(f"エラー発生: {program_id}, {e}")

driver.quit()
