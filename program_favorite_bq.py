import os
import json
import time
import re
import logging
import io
from datetime import datetime, timezone

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
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("お気に入り数 BigQuery版処理開始（UTC時間設定）")

# =========================
# 1. 設定と認証
# =========================
PROJECT_ID = 'tver-data'
DATASET_ID = 'tver_raw_data'
TABLE_ID = 'favorite_logs' 

try:
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]
except (KeyError, json.JSONDecodeError) as e:
    logger.error(f"環境変数エラー: {e}")
    raise

# 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
client = gspread.authorize(creds)
bq_client = bigquery.Client.from_service_account_info(service_account_info, project=PROJECT_ID)

# =========================
# 2. ブラウザ設定
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument(
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(options=chrome_options)

# =========================
# 3. メイン処理
# =========================
results_for_bq = []

try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    program_sheet = spreadsheet.worksheet("program_master_bq")
    rows = program_sheet.get_all_records()

    logger.info(f"シートから読み込んだ総行数: {len(rows)}行")

    for idx, row in enumerate(rows):
        # active列のチェック（大文字小文字を区別せずTRUEのみ対象）
        if str(row.get("active", "")).upper() != "TRUE":
            continue

        # 「番組URL」または「url」のどちらのカラム名にも対応できるように取得
        url = row.get("番組URL", row.get("url", ""))
        if not url or not isinstance(url, str):
            continue

        # 末尾のハッシュやスラッシュを考慮してIDを抽出
        program_id = url.split("?")[0].rstrip("/").split("/")[-1]

        # 見出し文字列の誤認、または不正なURLをスキップするガード構文
        if program_id in ["series_id", "url", "series"] or "tver.jp" not in url:
            logger.info(f"スキップ（ヘッダーまたは不正URL）: {url}")
            continue

        try:
            logger.info(f"処理開始: {program_id}")
            driver.get(url)
            time.sleep(5) 

            wait = WebDriverWait(driver, 15)
            elem = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[class^='FavoriteButton_count']")
                )
            )

            text = elem.text
            numbers = re.findall(r'[\d.,万]+', text)
            
            if not numbers:
                logger.warning(f"{program_id}: 数値が見つかりませんでした")
                continue

            val = numbers[0].replace(",", "")
            count = int(float(val.replace("万", "")) * 10000) if "万" in val else int(val)

            # --- BigQuery送信用リストに格納 (UTC時間) ---
            results_for_bq.append({
                "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "program_id": program_id,
                "favorite_count": count
            })
            logger.info(f"取得成功: {program_id} = {count} (UTC)")

        except Exception as e:
            logger.error(f"エラー発生 ({program_id}): {type(e).__name__} - {str(e).splitlines()[0]}")

    # =========================
    # BigQueryへ一括アップロード
    # =========================
    if results_for_bq:
        logger.info(f"BigQueryへ一括送信を開始します: {len(results_for_bq)}件")
        table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
        
        json_data = "\n".join([json.dumps(d) for d in results_for_bq])
        file_obj = io.StringIO(json_data)
        
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField("observed_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("program_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("favorite_count", "INTEGER", mode="REQUIRED"),
            ],
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition="WRITE_APPEND",
            autodetect=False
        )
        
        load_job = bq_client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result() # 完了待機
        logger.info(f"BigQuery({TABLE_ID})への書き込みがすべて完了しました！")
    else:
        logger.warning("送信対象のデータが0件でした。")

finally:
    if driver:
        driver.quit()
        logger.info("Chrome終了OK")

logger.info("全処理終了")
