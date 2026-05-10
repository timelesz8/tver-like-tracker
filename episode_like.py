import os
import json
import time
import io
import pandas as pd
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 設定項目（お気に入りの設定と統一） ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'
LOCATION = 'asia-northeast1'

# スプレッドシートのURL
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8/export?format=csv&gid=0"

def setup_driver():
    """GitHub Actionsで動かすためのChrome設定"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def get_tver_like_selenium(driver, episode_id):
    """Seleniumを使用してTVerからいいね数を取得"""
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        # 数字が表示されるまで待機
        wait = WebDriverWait(driver, 15)
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        
        like_text = element.text.replace(',', '')
        return int(like_text) if like_text.isdigit() else 0
    except Exception as e:
        print(f"Error fetching {episode_id}: {e}")
        return None

def upload_to_bigquery(data_list):
    """お気に入りのコードと同じ方式でBigQueryへアップロード"""
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY is missing")
        return

    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)

    # JSONL形式（1行1データ）に変換
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND",
    )

    try:
        load_job = client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result() # 完了待機
        print(f"Success: BigQuery({TABLE_ID}) へのロードに成功しました！")
    except Exception as e:
        print(f"BigQuery Load Error: {e}")

if __name__ == "__main__":
    # 日本時間 (JST)
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    # 1. スプレッドシートから対象を取得
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        # N列(active)がTRUEのものを抽出
        active_df = df[df['active'].astype(str).str.upper() == 'TRUE']
        # A列(episode_id)をリスト化
        target_ids = active_df['episode_id'].dropna().tolist()
        print(f"Target IDs: {target_ids}")
    except Exception as e:
        print(f"Spreadsheet Read Error: {e}")
        target_ids = []

    # 2. スクレイピング実行
    if target_ids:
        driver = setup_driver()
        results_for_bq = []
        try:
            for eid in target_ids:
                print(f"Processing: {eid}")
                count = get_tver_like_selenium(driver, eid)
                if count is not None:
                    results_for_bq.append({
                        "observed_at": now,
                        "episode_id": eid, 
                        "like_count": int(count)
                    })
                time.sleep(3)
        finally:
            driver.quit()

        # 3. BigQueryへ書き込み
        if results_for_bq:
            upload_to_bigquery(results_for_bq)
    else:
        print("No active episodes found.")
