"""
짠내로 편의점 행사 크롤러 v2
- pyony.com/{brand}/{YYYYMM}/ 에서 이번 달 행사 상품 수집
- Supabase cvs_sales 테이블에 저장
"""

import os, re, time, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent":"Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36","Accept-Language":"ko-KR,ko;q=0.9"}
NOW = datetime.now(timezone.utc)
YYYYMM = NOW.strftime("%Y%m")

BRANDS = {
    "cu":      f"https://pyony.com/brands/cu/{YYYYMM}/",
    "gs25":    f"https://pyony.com/brands/gs25/{YYYYMM}/",
    "seven":   f"https://pyony.com/brands/seven/{YYYYMM}/",
    "emart24": f"https://pyony.com/brands/emart24/{YYYYMM}/",
}

def detect_deal(t):
    for k in ["1+1","2+1","3+1","덤증정","증정","할인"]:
        if k in t: return k
    return "행사"

def parse_price(t):
    for n in re.findall(r"[\d,]+", t or ""):
        try:
            v = int(n.replace(",",""))
            if 100 <= v <= 100000: return v
        except: pass
    return 0

def detect_cat(name):
    n = name.lower()
    if any(k in n for k in ["음료","커피","물","주스","우유","콜라","사이다","이온","에너지"]): return "음료"
    if any(k in n for k in ["라면","컵라면","우동","국수"]): return "라면"
    if any(k in n for k in ["과자","초코","쿠키","칩","스낵","캔디","사탕","껌"]): return "과자"
    if any(k in n for k in ["아이스","빙과"]): return "아이스크림"
    if any(k in n for k in ["도시락","삼각김밥","샌드위치","김밥","햄버거"]): return "식품"
    if any(k in n for k in ["요거트","치즈","유제품"]): return "유제품"
    return "기타"

def crawl(brand, url):
    items = []
    for page in range(1, 21):
        purl = f"{url}?page={page}" if page > 1 else url
        try:
            res = requests.get(purl, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"  [ERR] page={page}: {e}"); break

        soup = BeautifulSoup(res.text, "html.parser")

        # 상품 링크에서 직접 추출 (pyony URL 패턴: /brands/{brand}/products/{id}/)
        links = soup.select(f"a[href*='/brands/{brand}/products/']")
        if not links:
            # 전체 products 링크 시도
            links = soup.select("a[href*='/products/']")

        if not links:
            print(f"  [WARN] {brand} page={page}: 상품 없음"); break

        for link in links:
            name = link.get_text(strip=True)
            if not name or len(name) < 2: continue
            # 부모 요소에서 가격/딜 정보 추출
            p = link.parent
            full = p.get_text(" ", strip=True) if p else name
            # 이미지
            img = ""
            img_el = (p or link).find("img")
            if img_el: img = img_el.get("src","")
            # 가격 파싱
            price_el = p.select_one("[class*='price']") if p else None
            price = parse_price(price_el.get_text() if price_el else full)

            items.append({
                "brand": brand,
                "name": name[:100],
                "price": price,
                "deal_type": detect_deal(full),
                "category": detect_cat(name),
                "img_url": img,
                "crawled_at": NOW.isoformat(),
            })

        print(f"  [{brand.upper()}] page={page}: {len(links)}개")

        next_btn = soup.select_one("a[rel='next']") or soup.select_one(".pagination .next a")
        if not next_btn: break
        time.sleep(1)

    # 중복 제거
    seen, unique = set(), []
    for i in items:
        if i["name"] not in seen:
            seen.add(i["name"]); unique.append(i)
    print(f"  [{brand.upper()}] 최종 {len(unique)}개")
    return unique

def upload(items):
    if not items: return
    brands = list(set(i["brand"] for i in items))
    for b in brands:
        supabase.table("cvs_sales").delete().eq("brand", b).execute()
    for i in range(0, len(items), 100):
        supabase.table("cvs_sales").insert(items[i:i+100]).execute()
    print(f"  ✅ {len(items)}개 업로드 완료")

def main():
    brand_env = os.environ.get("CRAWL_BRAND","")
    targets = {brand_env: BRANDS[brand_env]} if brand_env in BRANDS else BRANDS
    print(f"=== 크롤러 v2 | {YYYYMM} | {list(targets.keys())} ===")
    all_items = []
    for brand, url in targets.items():
        print(f"\n[{brand.upper()}] {url}")
        all_items.extend(crawl(brand, url))
        time.sleep(2)
    print(f"\n총 {len(all_items)}개")
    upload(all_items)

if __name__ == "__main__":
    main()
