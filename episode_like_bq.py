import os
import json
import time
import re
import logging
import io
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials
from google.cloud import bigquery

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# 0. ログ設定 (詳細に出すように変更)
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =========================
# 1. 設定と認証
# =========================
JST = timezone(timedelta(hours=+9), "JST")
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'

try:
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]
except Exception as e:
    logger.error(f"環境変数エラー: {e}")
    raise

# BigQuery / Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)
bq_client = bigquery.Client.from_service_account_info(service_account_info, project=PROJECT_ID)

# =========================
# BigQuery保存用関数 (スキーマ厳格版)
# =========================
def upload_to_bigquery(data_list):
    logger.info(f"BigQueryへ送信開始: {len(data_list)}件")
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    
    # 既存のテーブルスキーマを取得
    table = bq_client.get_table(table_ref)
    
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=table.schema, # 既存のREQUIRED設定をそのまま使う
        write_disposition="WRITE_APPEND",
    )
    
    try:
        load_job = bq_client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        result = load_job.result() # 完了を待つ
        logger.info(f"BigQuery送信完了。状態: {result.state}")
    except Exception as e:
        logger.error(f"BigQuery送信失敗: {e}")

# =========================
# 2. ブラウザ・メイン処理
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

results_for_bq = []
driver = webdriver.Chrome(options=chrome_options)

try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    episode_sheet = spreadsheet.worksheet("episode_master")
    rows = episode_sheet.get_all_records()
    logger.info(f"スプレッドシートから {len(rows)} 行読み込みました")

    for idx, row in enumerate(rows):
        active = str(row.get("active", "")).upper()
        url = row.get("url", "")
        if active != "TRUE" or not url:
            continue

        episode_id = url.rstrip("/").split("/")[-1]
        try:
            driver.get(url)
            time.sleep(5)
            wait = WebDriverWait(driver, 15)
            selector = "button[aria-label*='いいね'] [class^='IconButton_label']"
            elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            
            text = elem.text
            numbers = re.findall(r"[\d.,万]+", text)
            if not numbers: continue
            
            val = numbers[0].replace(",", "")
            count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val)

            results_for_bq.append({
                "observed_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S"), # 秒まで
                "episode_id": episode_id,
                "like_count": count
            })
            logger.info(f"データ取得完了: {episode_id} = {count}")
            
        except Exception as e:
            logger.warning(f"取得失敗 ({episode_id}): {e}")

    # まとめてアップロード
    if results_for_bq:
        upload_to_bigquery(results_for_bq)
    else:
        logger.warning("送信対象のデータが0件でした")

finally:
    driver.quit()
    logger.info("全処理終了")
