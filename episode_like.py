import os
import json
import time
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
import io
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

def get_tver_like_selenium(driver, episode_id):
    """
    Seleniumを使用してTVerのいいね数を取得
    """
    url = f"https://tver.jp/episodes/{episode_id}"
    try:
        driver.get(url)
        
        # 「いいね」ボタンの数値が表示されるまで最大10秒待機
        # セレクタは実際のTVerの構造（[class*="ActionButton_number"]等）に合わせて微調整してください
        wait = WebDriverWait(driver, 10)
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="ActionButton_number"]')))
        
        like_text = element.text.replace(',', '') # カンマを除去
        like_count = int(like_text) if like_text.isdigit() else 0
        
        print(f"Success: {episode_id} -> {like_count}")
        return like_count
    except Exception as e:
        print(f"Error fetching {episode_id}: {e}")
        return None

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # GitHub Actions環境では必須の設定
    return webdriver.Chrome(options=chrome_options)

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

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()
    
    # 追跡対象のエピソードID（実際はリストを動的に生成するようにしてください）
    target_ids = ["epXXXXXXXX"] 

    driver = setup_driver()
    results = []
    try:
        for eid in target_ids:
            count = get_tver_like_selenium(driver, eid)
            if count is not None:
                results.append({"episode_id": eid, "like_count": count, "observed_at": now})
            time.sleep(2)
    finally:
        driver.quit()

    if results:
        upload_to_bigquery(results)
