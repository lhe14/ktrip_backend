-- K-trip 운영 DB 스키마 (MySQL 8.0)
--
-- app/models/*.py (SQLAlchemy 모델)을 그대로 옮긴 DDL입니다.
-- 컬럼 순서/이름/제약조건은 ORM 모델과 1:1로 맞춰뒀으니, 이 스크립트로 만든 DB는
-- 코드 수정 없이 바로 app/main.py의 FastAPI 앱에 연결해서 쓸 수 있습니다.
--
-- 참고: 이제 테이블 생성/변경은 Alembic이 담당합니다 (alembic/versions/0001_initial_schema.py).
-- 실제로 DB에 스키마를 적용할 때는 이 파일 대신 `alembic upgrade head`를 쓰는 걸 추천합니다.
-- 이 schema.sql은 1) Python/Alembic 없이 SQL만으로 스키마를 검토·백업해야 할 때,
-- 2) 운영 DB 구조를 한눈에 문서처럼 보고 싶을 때 참고용으로 남겨둔 것으로,
-- alembic/versions/0001_initial_schema.py와 항상 같은 내용을 유지해야 합니다.

CREATE DATABASE IF NOT EXISTS ktrip
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ktrip;

-- ---------------------------------------------------------------
-- user  (app/models/user.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user` (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    email             VARCHAR(120) NOT NULL,
    nickname          VARCHAR(50)  NOT NULL,
    hashed_password   VARCHAR(200) NOT NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_email (email),
    UNIQUE KEY uq_user_nickname (nickname)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- place  (app/models/place.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS place (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    content_id        VARCHAR(20)  NOT NULL,          -- TourAPI contentId
    title             VARCHAR(200) NOT NULL,
    address           VARCHAR(300) NULL,
    area_code         VARCHAR(10)  NULL,
    mapx              DOUBLE NULL,                     -- 경도
    mapy              DOUBLE NULL,                     -- 위도
    first_image       VARCHAR(500) NULL,
    tel               VARCHAR(50)  NULL,
    content_type_id   VARCHAR(10)  NULL,
    cat1              VARCHAR(10)  NULL,
    cat2              VARCHAR(10)  NULL,
    cat3              VARCHAR(10)  NULL,
    theme_code        VARCHAR(30)  NULL,
    overview          TEXT NULL,
    score             DOUBLE NOT NULL DEFAULT 0.0,
    synced_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_place_content_id (content_id),
    KEY ix_place_area_code (area_code),
    KEY ix_place_theme_code (theme_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- theme_map  (app/models/place.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS theme_map (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    content_type_id   VARCHAR(10) NOT NULL,
    cat1              VARCHAR(10) NULL,
    cat2              VARCHAR(10) NULL,
    cat3              VARCHAR(10) NULL,
    theme_code        VARCHAR(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- review  (app/models/review.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    place_id          INT NOT NULL,
    user_id           INT NOT NULL,
    rating            INT NOT NULL,
    content           TEXT NULL,
    like_count        INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_review_place_id (place_id),
    KEY ix_review_user_id (user_id),
    CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_review_place FOREIGN KEY (place_id) REFERENCES place (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_review_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- review_like  (app/models/review.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_like (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    review_id         INT NOT NULL,
    user_id           INT NOT NULL,
    KEY ix_review_like_review_id (review_id),
    KEY ix_review_like_user_id (user_id),
    CONSTRAINT uq_review_like_user UNIQUE (review_id, user_id),
    CONSTRAINT fk_review_like_review FOREIGN KEY (review_id) REFERENCES review (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_review_like_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- board_post  (app/models/board.py)
-- category 값은 DB 제약이 아니라 app/models/board.py의 BoardCategory Enum
-- (qna/tips/review/companion)으로 애플리케이션 레벨에서 검증됩니다.
-- place_id/rating은 category='review'일 때만 쓰이고, 그 외에는 NULL입니다.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS board_post (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    user_id           INT NOT NULL,
    area_code         VARCHAR(10) NULL,
    category          VARCHAR(20) NOT NULL,
    title             VARCHAR(200) NOT NULL,
    content           TEXT NOT NULL,
    image_url         VARCHAR(500) NULL,
    place_id          INT NULL,
    rating            INT NULL,
    like_count        INT NOT NULL DEFAULT 0,
    comment_count     INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_board_post_user_id (user_id),
    KEY ix_board_post_area_code (area_code),
    KEY ix_board_post_category (category),
    KEY ix_board_post_place_id (place_id),
    CONSTRAINT ck_board_post_rating CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    CONSTRAINT fk_board_post_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_board_post_place FOREIGN KEY (place_id) REFERENCES place (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- board_post_companion  (app/models/board.py)
-- category='companion'인 게시글에만 1:1로 붙는 동행 모집 상세 정보
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS board_post_companion (
    post_id           INT PRIMARY KEY,
    destination       VARCHAR(100) NOT NULL,
    start_date        DATE NULL,
    end_date          DATE NULL,
    travelers_needed  INT NULL,
    travelers_joined  INT NOT NULL DEFAULT 1,
    CONSTRAINT fk_board_post_companion_post FOREIGN KEY (post_id) REFERENCES board_post (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- board_post_like  (app/models/board.py) - review_like와 동일한 패턴
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS board_post_like (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    post_id           INT NOT NULL,
    user_id           INT NOT NULL,
    KEY ix_board_post_like_post_id (post_id),
    KEY ix_board_post_like_user_id (user_id),
    CONSTRAINT uq_board_post_like_user UNIQUE (post_id, user_id),
    CONSTRAINT fk_board_post_like_post FOREIGN KEY (post_id) REFERENCES board_post (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_board_post_like_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- board_comment  (app/models/board.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS board_comment (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    post_id           INT NOT NULL,
    user_id           INT NOT NULL,
    content           TEXT NOT NULL,
    like_count        INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_board_comment_post_id (post_id),
    KEY ix_board_comment_user_id (user_id),
    CONSTRAINT fk_board_comment_post FOREIGN KEY (post_id) REFERENCES board_post (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_board_comment_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- board_comment_like  (app/models/board.py)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS board_comment_like (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    comment_id        INT NOT NULL,
    user_id           INT NOT NULL,
    KEY ix_board_comment_like_comment_id (comment_id),
    KEY ix_board_comment_like_user_id (user_id),
    CONSTRAINT uq_board_comment_like_user UNIQUE (comment_id, user_id),
    CONSTRAINT fk_board_comment_like_comment FOREIGN KEY (comment_id) REFERENCES board_comment (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_board_comment_like_user FOREIGN KEY (user_id) REFERENCES `user` (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 운영 조회 패턴에 맞춘 추가 복합 인덱스 (모델 구조 변경 없이 성능만 개선)
--   - 게시판: area_code + category로 필터링 후 최신순 정렬 (GET /board/posts)
--   - 리뷰: place_id로 최신 리뷰 나열 (GET /places/{id}/reviews)
--   - 장소: 지역+테마로 후보를 뽑는 일정 추천 쿼리 (GET /itinerary)
-- ---------------------------------------------------------------
CREATE INDEX ix_board_post_list ON board_post (area_code, category, created_at);
CREATE INDEX ix_review_place_created ON review (place_id, created_at);
CREATE INDEX ix_place_area_theme ON place (area_code, theme_code);
