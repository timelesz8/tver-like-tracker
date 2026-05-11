import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# (中略：データ取得部分。favorite_count などを取得するコード)

def upload_to_bigquery(data_list):
    # 認証設定
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)

    # テーブルID（画像から確認したテーブル名）
    table_id = f"{credentials.project_id}.tver_raw_data.favorite_logs"

    # ジョブの設定（成功しているコードに準拠）
    job_config = bigquery.LoadJobConfig(
        # 画像 のスキーマ定義を明示的に指定
        schema=[
            bigquery.SchemaField("observed_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("program_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("favorite_count", "INTEGER", mode="REQUIRED"),
        ],
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_APPEND",
        autodetect=False
    )

    try:
        # データの送信
        load_job = client.load_table_from_json(data_list, table_id, job_config=job_config)
        load_job.result()  # 完了を待機
        print(f"BigQueryアップロード成功: {table_id}")
    except Exception as e:
        print(f"BigQueryアップロードエラー: {e}")

# (中略：実行部分)
