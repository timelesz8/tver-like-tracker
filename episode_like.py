import os
import json
import time
import io
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.cloud import bigquery
from google.oauth2.service_account import Credentials
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
SPREADSHEET_ID = "1EFvUFSscwBhVhg9NtRWAnQw2pb60tVugJTjnn3vf2H8"

def setup_driver():
    """GitHub Actions環境で最も安定するブラウザ設定"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    # 普通のブラウザになりすます
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_tver_like_selenium(driver, episode_id):
    """TVerから「いいね」数を取得する。数字が出るまで粘り強く待機する。"""
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        # 要素が表示されるまで最大30秒待機
        wait = WebDriverWait(driver, 30)
        # クラス名に ActionButton_number を含む要素を探す
        element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        
        # 要素が見つかっても数字がロードされるまでラグがあるため、最大10秒ループで確認
        like_count = 0
        for _ in range(10):
            text = element.text.replace(',', '').strip()
            if text.isdigit():
                like_count = int(text)
                print(f"  -> Successfully scraped: {like_count}")
                return like_count
            time.sleep(1)
        
        return 0
    except Exception as e:
        print(f"  -> Error fetching {episode_id}: {str(e)[:50]}...")
        return None

def upload_to_bigquery(data_list):
    """取得したデータをBigQueryに一括保存する"""
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY is missing")
        return
    
    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
    
    # JSONL形式（改行区切りJSON）に変換
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND",
    )
    
    try:
        load_job = client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result()
        print(f"--- BigQuery Upload Success: {len(data_list)} rows ---")
    except Exception as e:
        print(f"BigQuery Upload Error: {e}")

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    # 1. スプレッドシートから対象IDを取得（一昨日の安定ロジック）
    try:
        key_info = json.loads(os.environ.get('GCP_SA_KEY'))
        creds = Credentials.from_service_account_info(key_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='episode_master!A:N').execute()
        values = result.get('values', [])
        
        target_ids = []
        if values:
            header = values[0]
            # 列名からインデックスを動的に特定
            id_idx = header.index('episode_id')
            active_idx = header.index('active')
            
            for row in values[1:]:
                if len(row) > active_idx:
                    eid = row[id_idx].strip()
                    # active列が "TRUE" のものだけ
                    if row[active_idx].strip().upper() == 'TRUE' and eid:
                        target_ids.append(eid)
        
        print(f"Target IDs identified: {target_ids}")
    except Exception as e:
        print(f"Sheet Read Error: {e}")
        target_ids = []

    # 2. スクレイピング実行
    if target_ids:
        driver = setup_driver()
        results = []
        try:
            for eid in target_ids:
                print(f"Scraping: {eid}")
                count = get_tver_like_selenium(driver, eid)
                
                if count is not None:
                    results.append({
                        "observed_at": now,
                        "episode_id": eid, 
                        "like_count": int(count)
                    })
                # 負荷軽減と安定のため5秒待機
                time.sleep(5)
        finally:
            driver.quit()

        # 3. BigQueryへ保存
        if results:
            upload_to_bigquery(results)
        else:
            print("No data collected.")
    else:
        print("No active episodes found in sheet.")
