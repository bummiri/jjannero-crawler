"""
짠내로 편의점 행사 크롤러
- 펴늬(pyony.com) 기반 4개 편의점 1+1/2+1 행사 상품 수집
- Supabase cvs_sales 테이블에 upsert
- GitHub Actions에서 매주 월요일 02:00 KST 실행
"""

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from supabase import create_client, Client

# ── Supabase 연결 ─────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── 설정 ──────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BRANDS = {
    "cu":       "https://pyony.com/brands/cu/",
    "gs25":     "https://pyony.com/brands/gs25/",
    "seven":    "https://pyony.com/brands/seven/",
    "emart24":  "https://pyony.com/brands/emart24/",
}

DEAL_MAP = {
    "1+1": "1+1",
    "2+1": "2+1",
    "3+1": "3+1",
    "덤증정": "덤증정",
    "할인": "할인",
}


def parse_price(text: str) -> int:
    """'1,800원' → 1800"""
    if not text:
        return 0
    cleaned = text.replace(",", "").replace("원", "").replace(" ", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return 0


def detect_deal(text: str) -> str:
    for key in DEAL_MAP:
        if key in text:
            return DEAL_MAP[key]
    return "행사"


def crawl_pyony(brand: str, url: str) -> list[dict]:
    """펴늬에서 브랜드별 행사 상품 파싱"""
    items = []
    page = 1

    while True:
        page_url = f"{url}?page={page}" if page > 1 else url
        try:
            res = requests.get(page_url, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"  [ERROR] {brand} page={page}: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")

        # 펴늬 상품 카드 파싱
        # 상품은 .product-item 또는 article 태그
        cards = soup.select(".product-item, article.item, .item-card, .prod-item")
        if not cards:
            # 대체 셀렉터 시도
            cards = soup.select("li[class*='product'], div[class*='product']")

        if not cards:
            print(f"  [WARN] {brand} page={page}: 상품 없음 (셀렉터 확인 필요)")
            break

        for card in cards:
            try:
                name_el = card.select_one(".product-name, .name, h3, h4, [class*='name']")
                price_el = card.select_one(".price, [class*='price']")
                deal_el  = card.select_one(".deal, .badge, [class*='deal'], [class*='badge'], [class*='type']")
                img_el   = card.select_one("img")
                cat_el   = card.select_one(".category, [class*='category'], [class*='cat']")

                name  = name_el.get_text(strip=True) if name_el else ""
                price = parse_price(price_el.get_text(strip=True)) if price_el else 0
                deal  = detect_deal(deal_el.get_text(strip=True) if deal_el else "")
                img   = img_el.get("src", "") if img_el else ""
                cat   = cat_el.get_text(strip=True) if cat_el else "기타"

                if not name:
                    continue

                items.append({
                    "brand":       brand,
                    "name":        name,
                    "price":       price,
                    "deal_type":   deal,
                    "category":    cat,
                    "img_url":     img,
                    "crawled_at":  datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                print(f"  [WARN] 파싱 오류: {e}")
                continue

        # 다음 페이지 확인
        next_btn = soup.select_one("a[rel='next'], .next, [class*='next']")
        if not next_btn or page >= 10:  # 최대 10페이지
            break
        page += 1
        time.sleep(1)  # 요청 간격

    print(f"  [{brand.upper()}] {len(items)}개 수집")
    return items


def upsert_to_supabase(items: list[dict]) -> None:
    """Supabase cvs_sales 테이블에 upsert"""
    if not items:
        return

    # 기존 데이터 삭제 후 새 데이터 삽입 (이번 주 데이터로 교체)
    brands = list(set(i["brand"] for i in items))
    for brand in brands:
        supabase.table("cvs_sales").delete().eq("brand", brand).execute()
        print(f"  [{brand.upper()}] 기존 데이터 삭제")

    # 배치 삽입 (100개씩)
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        result = supabase.table("cvs_sales").insert(batch).execute()
        print(f"  배치 {i//batch_size + 1}: {len(batch)}개 삽입")


def main():
    print(f"=== 짠내로 편의점 크롤러 시작 ===")
    print(f"실행 시각: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    all_items = []

    for brand, url in BRANDS.items():
        print(f"[{brand.upper()}] 크롤링 시작: {url}")
        items = crawl_pyony(brand, url)
        all_items.extend(items)
        time.sleep(2)  # 브랜드 간 딜레이

    print(f"\n총 수집: {len(all_items)}개")

    if all_items:
        print("\nSupabase 업로드 중...")
        upsert_to_supabase(all_items)
        print("✅ 업로드 완료")

        # 결과 리포트
        from collections import Counter
        brand_cnt = Counter(i["brand"] for i in all_items)
        deal_cnt  = Counter(i["deal_type"] for i in all_items)
        print("\n[브랜드별]")
        for b, c in brand_cnt.items():
            print(f"  {b.upper()}: {c}개")
        print("[행사 유형별]")
        for d, c in deal_cnt.items():
            print(f"  {d}: {c}개")
    else:
        print("⚠️ 수집된 데이터 없음 — 셀렉터 점검 필요")


if __name__ == "__main__":
    main()
