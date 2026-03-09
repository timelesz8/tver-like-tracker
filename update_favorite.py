# 既存のロジックに続けて、お気に入り数取得部分を追記
try:
    # ページ全体から「お気に入り数」という文字を含む要素を探す
    fav_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り数')]")
    fav_text = fav_elem.text  # 例: "お気に入り数31.9万"
    
    # 数値を抽出
    fav_numbers = re.findall(r'[\d.,万]+', fav_text)
    if fav_numbers:
        fav_raw = fav_numbers[0]
        # 「万」を数値に変換（必要に応じて調整）
        if "万" in fav_raw:
            favorite_count = int(float(fav_raw.replace("万", "")) * 10000)
        else:
            favorite_count = int(fav_raw.replace(",", ""))
    else:
        favorite_count = 0
except Exception as e:
    print(f"お気に入り数取得失敗 ({episode_id}): {e}")
    favorite_count = 0
