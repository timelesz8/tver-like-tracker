import os
import json
import io
import logging
from datetime import datetime, timedelta, timezone
from google.oauth2.service_account import Credentials
from google.cloud import bigquery

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 設定
JST = timezone(timedelta(hours=+9), "JST")
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'

# 実験データ
test_data = [
    {
        "observed_at": "2026-05-11T14:10:35", # ISO形式
        "episode_id": "epvhm6bzte",
        "like_count": 3885
    }
]

try:
    # 認証
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    bq_client = bigquery.Client.from_service_account_info(service_account_info, project=PROJECT_ID)
    
    # 送信処理
    logger.info(f"BigQueryへ実験データを送信します: {test_data}")
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    table = bq_client.get_table(table_ref) # スキーマ取得
    
    json_data = "\n".join([json.dumps(d) for d in test_data])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=table.schema,
        write_disposition="WRITE_APPEND",
    )
    
    load_job = bq_client.load_table_from_file(file_obj, table_ref, job_config=job_config)
    result = load_job.result() # 完了待機
    logger.info(f"実験成功！ BigQueryの状態: {result.state}")

except Exception as e:
    logger.error(f"実験失敗: {e}")
