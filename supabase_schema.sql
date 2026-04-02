-- =============================================
-- 짠내로 Supabase 스키마
-- Supabase SQL Editor에 붙여넣고 실행하세요
-- =============================================

-- 편의점 행사 상품 테이블
CREATE TABLE IF NOT EXISTS cvs_sales (
  id          BIGSERIAL PRIMARY KEY,
  brand       TEXT NOT NULL,          -- cu | gs25 | seven | emart24
  name        TEXT NOT NULL,          -- 상품명
  price       INTEGER DEFAULT 0,      -- 가격 (원)
  deal_type   TEXT NOT NULL,          -- 1+1 | 2+1 | 3+1 | 덤증정 | 할인
  category    TEXT DEFAULT '기타',    -- 음료 | 식품 | 과자 | 라면 | 아이스크림 | 유제품 | 기타
  img_url     TEXT DEFAULT '',        -- 상품 이미지 URL
  crawled_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 (조회 성능)
CREATE INDEX IF NOT EXISTS idx_cvs_sales_brand ON cvs_sales(brand);
CREATE INDEX IF NOT EXISTS idx_cvs_sales_deal  ON cvs_sales(deal_type);
CREATE INDEX IF NOT EXISTS idx_cvs_sales_crawled ON cvs_sales(crawled_at DESC);

-- RLS(Row Level Security) 비활성화 — 읽기 전용 공개 데이터
ALTER TABLE cvs_sales DISABLE ROW LEVEL SECURITY;

-- 익명 읽기 허용 (짠내로에서 조회용)
GRANT SELECT ON cvs_sales TO anon;
GRANT SELECT ON cvs_sales TO authenticated;

-- 확인용 조회
SELECT brand, deal_type, COUNT(*) as cnt
FROM cvs_sales
GROUP BY brand, deal_type
ORDER BY brand, deal_type;
