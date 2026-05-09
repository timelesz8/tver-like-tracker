import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'favorite_logs'
LOCATION = 'asia-northeast1' # ← 東京に設定している場合はここが必要

def get_tver_favorite(program_id):
    # 本来の取得ロジック（そのまま維持してください）
    return 0 

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY が設定されていません")
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info)
    table_full_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # ロケーションを明示的に指定してデータを挿入
    errors = client.insert_rows_json(table_full_id, data_list, location=LOCATION)
    
    if errors == []:
        print(f"Success: BigQuery({TABLE_ID}) への書き込み完了！")
    else:
        # 詳細なエラーを出力するように変更
        for error in errors:
            print(f"Detailed BigQuery Error: {error}")

if __name__ == "__main__":
    target_programs = ["ep1a6zd4e3"]
    results_for_bq = []
    now = datetime.now().isoformat()

    for pid in target_programs:
        # ここで実際の取得処理を呼び出す
        count = 100 # テスト用
        results_for_bq.append({
            "observed_at": now,
            "program_id": pid,
            "favorite_count": count
        })

    if results_for_bq:
        upload_to_bigquery(results_for_bq)
