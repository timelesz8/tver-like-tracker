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

# お気に入り数を取得する関数（中身はあなたの既存コードを維持してください）
def get_tver_favorite(program_id):
    # ここに元の取得ロジックが入ります
    return 100 

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY is missing")
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    
    # データの保存先テーブルを指定
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)

    # 無料枠対応：JSONL形式（1行1データの文字列）に変換
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)

    # ロード設定
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND", # 既存データに追記する設定
    )

    try:
        # ファイルとしてBigQueryへロードを実行
        load_job = client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result() # 完了を待つ
        print(f"Success: BigQuery({TABLE_ID}) へのロードに成功しました！")
    except Exception as e:
        print(f"BigQuery Load Error: {e}")

if __name__ == "__main__":
    # 対象の番組IDリスト（ここはご自身の管理しているものに合わせてください）
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
