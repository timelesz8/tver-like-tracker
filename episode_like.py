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
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    # 完全に普通のブラウザになりすますための設定
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    # 検知回避のためのJavaScript実行
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
        """
    })
    return driver

def get_tver_like_selenium(driver, episode_id):
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        # サイト側の読み込み待ち時間を十分に確保（最大20秒）
        wait = WebDriverWait(driver, 20)
        
        # クラス名の一部に "ActionButton_number" が含まれる要素を待機
        element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        
        # 取得したテキストを確認
        like_text = element.text.replace(',', '').strip()
        
        if like_text.isdigit():
            print(f"Success: {episode_id} -> {like_text}")
            return int(like_text)
        else:
            print(f"Wait for digit: {episode_id} currently shows '{like_text}'")
            # 数字が出るまで最大5秒追加で粘る
            for _ in range(5):
                time.sleep(1)
                like_text = element.text.replace(',', '').strip()
                if like_text.isdigit():
                    return int(like_text)
            return 0
            
    except Exception as e:
        print(f"Error fetching {episode_id}: {type(e).__name__}")
        return None

def upload_to_bigquery(data_list):
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
        load_job = client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result()
    except Exception as e:
        print(f"BigQuery Upload Error: {e}")

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()

    # --- シート読み込み ---
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
            id_idx = header.index('episode_id')
            active_idx = header.index('active')
            
            for row in values[1:]:
                if len(row) > active_idx:
                    eid = row[id_idx].strip()
                    is_active = row[active_idx].strip().upper() == 'TRUE'
                    if is_active and eid:
                        target_ids.append(eid)
        
        print(f"Target IDs identified: {target_ids}")
    except Exception as e:
        print(f"Sheet Read Error: {e}")
        target_ids = []

    # --- 実行 ---
    if target_ids:
        driver = setup_driver()
        results = []
        try:
            for eid in target_ids:
                print(f"Processing: {eid}")
                count = get_tver_like_selenium(driver, eid)
                if count is not None:
                    results.append({
                        "observed_at": now,
                        "episode_id": eid, 
                        "like_count": int(count)
                    })
                time.sleep(5) # 念のため間隔を少し広げました
        finally:
            driver.quit()

        if results:
            upload_to_bigquery(results)
            print(f"Final Success: {len(results)} rows saved.")
    else:
        print("No targets found.")
