import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery
import io

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'favorite_logs'
LOCATION = 'asia-northeast1'

def get_tver_favorite(program_id):
    # あなたの元の取得ロジック（そのままここに）
    return 100 

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'):
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)

    # 【重要】無料枠でも動く「ロード」形式に変換
    # データをJSON文字列にしてメモリ上に保存
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
    )

    try:
        load_job = client.load_table_from_file(
            file_obj, table_ref, job_config=job_config
        )
        load_job.result()  # 完了まで待機
        print(f"Success: BigQuery({TABLE_ID}) へのロード完了！")
    except Exception as e:
        print(f"Detailed BigQuery Error: {e}")

if __name__ == "__main__":
    target_programs = ["ep1a6zd4e3"]
    results_for_bq = []
    now = datetime.now().isoformat()

    for pid in target_programs:
        count = get_tver_favorite(pid)
        results_for_bq.append({
            "observed_at": now,
            "program_id": pid,
            "favorite_count": count
        })

    if results_for_bq:
        upload_to_bigquery(results_for_bq)
