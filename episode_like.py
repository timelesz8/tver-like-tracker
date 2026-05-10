import os
import json
import time
import re
import logging
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials

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

logger.info("処理開始")
logger.debug(f"LOG_LEVEL={LOG_LEVEL}")


# =========================
# 1. 設定と認証
# =========================

JST = timezone(timedelta(hours=+9), "JST")

try:
    service_account_info = json.loads(os.environ["GCP_SA_KEY"])
    SPREADSHEET_ID = os.environ["TVER_DATA_SHEET_ID"]

    logger.debug("環境変数の読み込みOK")
    logger.debug(f"SPREADSHEET_ID={SPREADSHEET_ID}")

except KeyError as e:
    logger.error(f"必要な環境変数がありません: {e}")
    raise

except json.JSONDecodeError as e:
    logger.error(f"GCP_SA_KEY のJSON形式が不正です: {e}")
    raise


scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

try:
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(creds)
    logger.info("Google認証OK")

except Exception as e:
    logger.error(f"Google認証エラー: {e}")
    raise


# =========================
# シート接続
# =========================

try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    logger.info("スプレッドシート接続OK")

    # エピソードいいね用のマスタシート
    episode_sheet = spreadsheet.worksheet("episode_master")
    logger.info("episode_master シート接続OK")

except Exception as e:
    logger.error(f"episode_master への接続に失敗しました: {e}")
    raise


try:
    like_sheet = spreadsheet.worksheet("like_data")
    logger.info("elike_data シート接続OK")

except Exception:
    logger.warning("like_data シートが無いので作成します")
    like_sheet = spreadsheet.add_worksheet(
        title="like_data",
        rows="1000",
        cols="10",
    )
    like_sheet.append_row(["datetime", "episode_id", "like_count"])
    logger.info("like_data シート作成OK")


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

driver = None

try:
    logger.info("Chrome起動開始")
    driver = webdriver.Chrome(options=chrome_options)
    logger.info("Chrome起動OK")

except Exception as e:
    logger.error(f"Chrome起動エラー: {e}")
    raise


# =========================
# 3. メイン処理
# =========================

try:
    rows = episode_sheet.get_all_records()

    logger.info(f"シートから読み込んだ総行数: {len(rows)}行")

    if len(rows) > 0:
        logger.debug(f"1行目のデータ形式サンプル: {rows[0]}")
        logger.debug(f"ヘッダー一覧: {list(rows[0].keys())}")

    processed_count = 0
    success_count = 0
    error_count = 0
    skipped_inactive_count = 0
    skipped_no_url_count = 0

    for idx, row in enumerate(rows, start=2):
        logger.debug("========================================")
        logger.debug(f"{idx}行目の処理開始")
        logger.debug(f"row={row}")

        active_value = str(row.get("active", "")).upper()

        if active_value != "TRUE":
            skipped_inactive_count += 1
            logger.debug(
                f"{idx}行目をスキップ: active が TRUE ではありません "
                f"(active={row.get('active', '')})"
            )
            continue

        url = row.get("url", "")

        if not url:
            skipped_no_url_count += 1
            logger.warning(f"{idx}行目をスキップ: 番組URL が空です")
            continue

        episode_id = url.rstrip("/").split("/")[-1]
        processed_count += 1

        try:
            logger.info(f"処理開始: {episode_id}")
            logger.debug(f"対象URL: {url}")

            driver.get(url)

            logger.debug("ページアクセス完了。5秒待機します")
            time.sleep(5)

            logger.debug(f"現在URL: {driver.current_url}")
            logger.debug(f"ページタイトル: {driver.title}")

            wait = WebDriverWait(driver, 15)

            selector = "button[aria-label*='いいね'] [class^='IconButton_label']"
            logger.debug(f"いいね要素の取得開始: selector={selector}")

            elem = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, selector)
                )
            )

            text = elem.text
            logger.debug(f"取得したいいね表示テキスト: {text!r}")

            # 数値抽出（3.5万 -> 35000）
            numbers = re.findall(r"[\d.,万]+", text)
            logger.debug(f"抽出した数値候補: {numbers}")

            if not numbers:
                raise Exception("いいね数が見つかりませんでした")

            val = numbers[0].replace(",", "")
            logger.debug(f"変換前の値: {val}")

            if "万" in val:
                count = int(float(val.replace("万", "")) * 10000)
            else:
                count = int(val)

            logger.debug(f"変換後のいいね数: {count}")

            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            logger.debug(f"書き込み日時: {now}")

            like_sheet.append_row([now, episode_id, count])

            success_count += 1
            logger.info(f"取得成功: {episode_id} = {count}")

        except Exception as e:
            error_count += 1

            screenshot_path = f"error_like_{episode_id}.png"

            try:
                driver.save_screenshot(screenshot_path)
                logger.error(
                    f"エラー発生: {episode_id}, {e} / "
                    f"スクリーンショット保存: {screenshot_path}"
                )

            except Exception as screenshot_error:
                logger.error(
                    f"エラー発生: {episode_id}, {e} / "
                    f"スクリーンショット保存にも失敗: {screenshot_error}"
                )

    logger.info("集計結果")
    logger.info(f"処理対象: {processed_count}件")
    logger.info(f"成功: {success_count}件")
    logger.info(f"エラー: {error_count}件")
    logger.info(f"active以外でスキップ: {skipped_inactive_count}件")
    logger.info(f"URLなしでスキップ: {skipped_no_url_count}件")

finally:
    if driver:
        driver.quit()
        logger.info("Chrome終了OK")

logger.info("全処理終了")
