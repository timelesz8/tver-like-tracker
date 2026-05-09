import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'favorite_logs'

def get_tver_favorite(program_id):
    """TVerからお気に入り数を取得する関数"""
    url = f"https://statics.tver.jp/content/episode/{program_id}.json" # 例としてのURL構造
    try:
        response = requests.get(url)
        data = response.json()
        # 実際のJSON構造に合わせて調整（例: data['favorite_count']）
        return data.get('favorite_count', 0)
    except:
        return 0

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
    # ここに取得したい番組IDのリストを入れる
    target_programs = ["ep1a6zd4e3"] # 画像に基づいた例
    
    results_for_bq = []
    now = datetime.now().isoformat()

    for pid in target_programs:
        count = get_tver_favorite(pid)
        results_for_bq.append({
            "observed_at": now,
            "program_id": pid,
            "favorite_count": count
        })
        print(f"Program {pid}: {count}")

    if results_for_bq:
        upload_to_bigquery(results_for_bq)
