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
# あなたのスプレッドシートのCSV出力URL
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8/export?format=csv&gid=0"

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def get_tver_like_selenium(driver, episode_id):
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        like_text = element.text.replace(',', '')
        return int(like_text) if like_text.isdigit() else 0
    except Exception as e:
        print(f"Error fetching {episode_id}: {e}")
        return None

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'): return
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
    client.load_table_from_file(file_obj, table_ref, job_config=job_config).result()

def extract_id_from_url(url):
    if pd.isna(url): return None
    match = re.search(r'/episodes/([^/?]+)', url)
    return match.group(1) if match else None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    # スプレッドシートを読み込んで、N列(active)がTrueのものだけ抽出
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        # N列が「TRUE」という文字列、または真偽値のTrueである行をフィルタ
        active_df = df[df['active'].astype(str).str.upper() == 'TRUE'].copy()
        active_df['extracted_id'] = active_df['url'].apply(extract_id_from_url)
        target_ids = active_df['extracted_id'].dropna().tolist()
        print(f"Targeting active episodes: {target_ids}")
    except Exception as e:
        print(f"Sheet Read Error: {e}")
        target_ids = []

    if target_ids:
        driver = setup_driver()
        results = []
        try:
            for eid in target_ids:
                print(f"Processing: {eid}")
                count = get_tver_like_selenium(driver, eid)
                if count is not None:
                    results.append({
                        "episode_id": eid, 
                        "like_count": int(count), 
                        "observed_at": now
                    })
                time.sleep(3)
        finally:
            driver.quit()

        if results:
            upload_to_bigquery(results)
            print(f"Successfully updated {len(results)} episodes.")
    else:
        print("No active episodes found in sheet.")
