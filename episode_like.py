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
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # --- GitHub Actions 安定化のための追加設定 ---
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    return webdriver.Chrome(options=chrome_options)

def get_tver_like_selenium(driver, episode_id):
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        # 画面が読み込まれるまで少し待機
        wait = WebDriverWait(driver, 15)
        # いいね数の要素（ActionButton_numberクラス）を探す
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        like_text = element.text.replace(',', '')
        
        if like_text.isdigit():
            return int(like_text)
        else:
            # 数字が取得できなかった場合（"いいね"という文字だけの時など）
            print(f"Warning: Could not parse like count for {episode_id}: {like_text}")
            return 0
            
    except Exception as e:
        print(f"Error fetching {episode_id}: {e}")
        return None

def upload_to_bigquery(data_list):
    if not os.environ.get('GCP_SA_KEY'):
        print("Error: GCP_SA_KEY is missing")
        return
    key_info = json.loads(os.environ.get('GCP_SA_KEY'))
    client = bigquery.Client.from_service_account_info(key_info, project=PROJECT_ID, location=LOCATION)
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
    
    # 改行区切りJSON（JSONL）形式に変換
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND",
    )
    
    try:
        load_job = client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result() # 完了まで待機
    except Exception as e:
        print(f"BigQuery Upload Error: {e}")

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    try:
        # --- スプレッドシート読み込み ---
        key_info = json.loads(os.environ.get('GCP_SA_KEY'))
        creds = Credentials.from_service_account_info(key_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='episode_master!A:N').execute()
        values = result.get('values', [])
        
        if not values:
            print("No data found in sheet.")
            target_ids = []
        else:
            header = values[0]
            try:
                id_idx = header.index('episode_id')
                active_idx = header.index('active')
                
                target_ids = []
                for row in values[1:]:
                    if len(row) > active_idx:
                        eid = row[id_idx].strip()
                        # N列(active)が "TRUE" のものだけ抽出
                        is_active = row[active_idx].strip().upper() == 'TRUE'
                        if is_active and eid:
                            target_ids.append(eid)
            except ValueError as e:
                print(f"Required columns (episode_id or active) not found: {e}")
                target_ids = []

        print(f"Target IDs identified: {target_ids}")

    except Exception as e:
        print(f"Sheet Read Error: {e}")
        target_ids = []

    # --- スクレイピングと保存の実行 ---
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
                # TVerサーバーへの負荷軽減
                time.sleep(3)
        finally:
            driver.quit()

        if results:
            upload_to_bigquery(results)
            print(f"Success: {len(results)} rows uploaded to BigQuery.")
        else:
            print("No data collected from TVer.")
    else:
        print("No active episodes to process. Check your Google Sheet N-column.")
