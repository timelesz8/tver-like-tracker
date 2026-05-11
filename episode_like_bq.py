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
# 0. ログ設定
# =========================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =========================
# 1. 設定と認証
# =========================
JST = timezone(timedelta(hours=+9), "JST")

# BigQuery設定
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'episode_like_logs'
LOCATION = 'asia-northeast1'

try:
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]
except KeyError as e:
    logger.error(f"環境変数不足: {e}")
    raise

# Google Sheets認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)

# BigQueryクライアント作成
bq_client = bigquery.Client.from_service_account_info(service_account_info, project=PROJECT_ID)

# =========================
# BigQuery保存用関数
# =========================
def upload_to_bigquery(data_list):
    """取得したデータをBigQueryに一括保存"""
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition="WRITE_APPEND",
    )
    try:
        load_job = bq_client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result()
        logger.info(f"BigQueryへのアップロード成功: {len(data_list)}件")
    except Exception as e:
        logger.error(f"BigQueryアップロードエラー: {e}")

# =========================
# 2. ブラウザ設定
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)

# =========================
# 3. メイン処理
# =========================
results_for_bq = []

try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    episode_sheet = spreadsheet.worksheet("episode_master")
    rows = episode_sheet.get_all_records()

    for idx, row in enumerate(rows, start=2):
        active_value = str(row.get("active", "")).upper()
        url = row.get("url", "")
        if active_value != "TRUE" or not url:
            continue

        episode_id = url.rstrip("/").split("/")[-1]
        
        try:
            logger.info(f"取得中: {episode_id}")
            driver.get(url)
            time.sleep(5)
            
            wait = WebDriverWait(driver, 15)
            selector = "button[aria-label*='いいね'] [class^='IconButton_label']"
            elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            
            # 数値抽出
            text = elem.text
            numbers = re.findall(r"[\d.,万]+", text)
            if not numbers: continue
            
            val = numbers[0].replace(",", "")
            count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val)

            # BigQuery用データ作成
            results_for_bq.append({
                "observed_at": datetime.now(JST).isoformat(),
                "episode_id": episode_id,
                "like_count": count
            })
            
        except Exception as e:
            logger.error(f"エラー ({episode_id}): {e}")

    # 最後に一括アップロード
    if results_for_bq:
        upload_to_bigquery(results_for_bq)

finally:
    driver.quit()
    logger.info("全処理終了")
