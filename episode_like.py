import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'
LOCATION = 'asia-northeast1'

def get_tver_like(episode_id):
    # 既存の取得ロジックをここに維持してください
    return 200

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'):
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    
    # 【ここを修正】クライアントを作る段階でロケーションを指定します
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    
    table_full_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # location引数を削除しました
    errors = client.insert_rows_json(table_full_id, data_list)
    
    if errors == []:
        print(f"Success: BigQuery({TABLE_ID}) への書き込み完了！")
    else:
        for error in errors:
            print(f"Detailed BigQuery Error: {error}")

if __name__ == "__main__":
    target_episodes = ["sr1bzatukq"]
    results_for_bq = []
    now = datetime.now().isoformat()

    for eid in target_episodes:
        count = get_tver_like(eid)
        results_for_bq.append({
            "observed_at": now,
            "episode_id": eid,
            "like_count": count
        })

    if results_for_bq:
        upload_to_bigquery(results_for_bq)
