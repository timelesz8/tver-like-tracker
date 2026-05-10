import gspread
import re
import time
import requests  # GASへの通知用に追加
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from selenium import webdriver
@@ -12,6 +13,9 @@
# 1. 設定と認証
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]
# GASのウェブアプリURL（GitHubのSecretsに追加してください）
gas_webhook_url = os.environ.get("GAS_WEBAPP_URL")

JST = timezone(timedelta(hours=+9), 'JST')

creds = Credentials.from_service_account_info(
@@ -38,12 +42,10 @@ def is_already_fetched_this_hour(sheet):
print(f"チェックエラー: {e}")
return False

# GASからの強制トリガーの場合はスキップを無効にしたい場合はここを調整
if is_already_fetched_this_hour(like_sheet):
print("直近30分以内に実行済みのためスキップします。")
exit()
# ---------------------------------



# 2. ブラウザ設定
chrome_options = Options()
@@ -56,17 +58,18 @@ def is_already_fetched_this_hour(sheet):

# 3. メイン処理
rows = url_sheet.get_all_records()
success_count = 0

for idx, row in enumerate(rows):
    # active列(O列)がTRUEの行のみ処理
    # active列がTRUEの行のみ処理
if str(row.get("active", "")).upper() != "TRUE":
continue

url = row.get("url", "")
if not url: continue

episode_id = url.split("/")[-1]
    row_number = idx + 2  # ヘッダー分を考慮したスプレッドシート上の行番号
    row_number = idx + 2  # ヘッダー分

try:
driver.get(url)
@@ -84,15 +87,22 @@ def is_already_fetched_this_hour(sheet):
now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
like_sheet.append_row([now, episode_id, like])
print(f"取得成功: {episode_id} = {like}")
        success_count += 1

except Exception as e:
print(f"エラー発生: {episode_id}, {e}")
        # 列の移動に合わせて修正
        # active(O列) = 14列目, end_date(Q列) = 16列目, days_active(Q列) = 17列目
today = datetime.now(JST).strftime("%Y-%m-%d")
url_sheet.update_cell(row_number, 14, "FALSE") # O列: active
url_sheet.update_cell(row_number, 16, today)    # Q列: end_date
        # R列(days_active)はスプレッドシートの関数が自動計算するため更新不要
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
