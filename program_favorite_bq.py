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
            logger.info(f"スキ
