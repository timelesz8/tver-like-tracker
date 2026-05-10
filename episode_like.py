import os
import json
import time
import io
import pandas as pd
import re
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 設定項目 ---
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'
LOCATION = 'asia-northeast1'
# スプレッドシートのCSVエクスポートURL
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8/export?format=csv&gid=0"

def setup_driver():
    """GitHub Actions環境用のChrome設定"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def get_tver_like_selenium(driver, episode_id):
    """Seleniumでいいね数を取得"""
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        # クラス名に ActionButton_number を含む要素を待機
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        like_text = element.text.replace(',', '')
        return int(like_text) if like_text.isdigit() else 0
    except Exception as e:
        print(f"Error fetching {episode_id}: {e}")
        return None

def upload_to_bigquery(data_list):
    """BigQueryへの書き込み処理"""
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY is missing")
        return
    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)

    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND",
    )
    try:
        client.load_table_from_file(file_obj, table_ref, job_config=job_config).result()
        print(f"Success: BigQuery({TABLE_ID}) へのロードに成功しました。")
    except Exception as e:
        print(f"BigQuery Load Error: {e}")

def extract_id_from_url(url):
    """URLからIDを抽出（D列のURLを利用）"""
    if pd.isna(url): return None
    match = re.search(r'/episodes/([^/?]+)', url)
    return match.group(1) if match else None

if __name__ == "__main__":
    # 日本時間 (JST)
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    # スプレッドシートからデータを取得（お気に入りのロジックに準拠）
    try:
        # スプレッドシートをCSVとして読み込み
        df = pd.read_csv(SHEET_CSV_URL)
        
        # N列(active)がTrueの行を抽出
        # 文字列として比較することで確実に判定
        active_df = df[df['active'].astype(str).str.upper() == 'TRUE'].copy()
        
        # D列(url)からIDを抽出、またはA列(episode_id)を使用
        # ここではより確実なD列からの抽出を優先します
        active_df['extracted_id'] = active_df['url'].apply(extract_id_from_url)
        target_ids = active_df['extracted_id'].dropna().tolist()
        
        print(f"Active IDs found: {target_ids}")
    except Exception as e:
        print(f"Spreadsheet Load Error: {e}")
        target_ids = []

    if target_ids:
        driver = setup_driver()
        results = []
        try:
            for eid in target_ids:
                print(f"Checking: {eid}")
                count = get_tver_like_selenium(driver, eid)
                if count is not None:
                    results.append({
                        "observed_at": now,
                        "episode_id": eid, 
                        "like_count": int(count)
                    })
                time.sleep(3) # サーバー負荷軽減
        finally:
            driver.quit()

        if results:
            upload_to_bigquery(results)
    else:
        print("No active episodes found to process.")
