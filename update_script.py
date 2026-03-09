import os
import json
import gspread
from google.oauth2.service_account import Credentials

# 1. GitHub Secretsから環境変数を取得
# 金庫の中身を取り出すイメージです
service_account_info = json.loads(os.environ["GCP_SA_KEY"])
spreadsheet_id = os.environ["TVER_DATA_SHEET_ID"]

# 2. 認証設定（Google Cloudと接続）
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)

# 3. スプレッドシート「TVerdata」を開いて書き込む
try:
    # 最初のシート（sheet1）を選択
    sheet = client.open_by_key(spreadsheet_id).sheet1
    
    # テスト用のデータを1行追加
    sheet.append_row(["実行日時", "ステータス", "備考"])
    sheet.append_row(["2026-03-09", "GitHub Actionsから接続成功！", "TVer初期モデル起動"])
    
    print("スプレッドシートへの書き込みに成功しました！")
except Exception as e:
    print(f"エラーが発生しました: {e}")
