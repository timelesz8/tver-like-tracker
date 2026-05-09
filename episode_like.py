import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'

def get_tver_like(episode_id):
    """TVerからいいね数を取得する関数"""
    # 実際の取得ロジック（SeleniumやAPI）に置き換えてください
    # ここでは例としてダミー値を返します
    return 100 

def upload_to_bigquery(data_list):
    """BigQueryに直接データを送る関数"""
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY が設定されていません")
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info)
    table_full_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    errors = client.insert_rows_json(table_full_id, data_list)
    if errors == []:
        print(f"Success: BigQuery({TABLE_ID}) への直接書き込み完了！")
    else:
        print(f"BigQuery Error: {errors}")

if __name__ == "__main__":
    # ここに取得したいエピソードIDのリストを入れる
    target_episodes = ["sr1bzatukq"] # 画像に基づいた例
    
    results_for_bq = []
    now = datetime.now().isoformat()

    for eid in target_episodes:
        count = get_tver_like(eid)
        results_for_bq.append({
            "observed_at": now,
            "episode_id": eid,
            "like_count": count
        })
        print(f"Episode {eid}: {count}")

    if results_for_bq:
        upload_to_bigquery(results_for_bq)
