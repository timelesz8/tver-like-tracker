# 既存のロジックに続けて、お気に入り数取得部分を追記
try:
        # 「お気に入り登録」というテキストを含む要素を探す
        # その要素の親（または兄弟要素）に数値が含まれているはずです
        fav_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'お気に入り登録')]")
        
        # 今回は「お気に入り登録」という文字の後に数値が来る構造と仮定して、
        # その要素が含まれる大きなブロックのテキストを取得します
        parent = fav_elem.find_element(By.XPATH, "../..") # 構造に合わせて .. の数を調整してください
        text = parent.text
        
        print(f"発見したお気に入りテキスト: {text}")
        
        # 数値抽出 (例: 18.6万)
        numbers = re.findall(r'[\d.,万]+', text)
        
        if numbers:
            fav_raw = numbers[0]
            if "万" in fav_raw:
                favorite_count = int(float(fav_raw.replace("万", "")) * 10000)
            else:
                favorite_count = int(fav_raw.replace(",", ""))
            print(f"取得したお気に入り数: {favorite_count}")
        else:
            favorite_count = 0
            
    except Exception as e:
        print(f"お気に入り数取得失敗: {e}")
        favorite_count = 0
