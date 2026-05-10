if __name__ == "__main__":
    # 1. 実行時刻（日本時間）
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).isoformat()
    
    # 2. 取得したいエピソードIDのリスト
    # ※ここを空にせず、まずはテストしたいIDを入れてみてください
    target_episode_ids = ["epXXXXXXXX", "epYYYYYYYY"] 

    # 3. Seleniumの起動
    driver = setup_driver()
    results = []
    
    try:
        for eid in target_episode_ids:
            # 前に作った Selenium 取得関数を呼び出す
            count = get_tver_like_selenium(driver, eid)
            if count is not None:
                results.append({
                    "episode_id": eid,
                    "like_count": int(count),
                    "observed_at": now
                })
            time.sleep(3) # TVerに優しく
    finally:
        driver.quit()

    # 4. ここで初めて BigQuery にデータが飛ぶ！
    if results:
        upload_to_bigquery(results)
    else:
        print("No data to upload.")
