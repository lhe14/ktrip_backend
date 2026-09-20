"""
공모전 데모 화면을 채우기 위한 더미데이터 삽입 스크립트.

F:\\K_trip\\Data\\output\\{users,board,review}_en.xlsx 에 있는 데이터 중 일부만 뽑아서 넣는다.
(엑셀 전체를 다 옮기는 게 아니라, 게시판/리뷰 화면이 비어 보이지 않을 정도만 - 자세한 배경은
대화에서 설명한 대로 엑셀 스키마가 지금 DB보다 훨씬 풍부해서 전체 이관은 하지 않기로 함)

실행 (프로젝트 루트에서):
    python -m scripts.import_dummy_data

필요 패키지: pandas, openpyxl (없으면 pip install pandas openpyxl)

반영 범위:
- user: 엑셀 20명 전부 (이메일/닉네임만 사용, 비밀번호는 전부 DEMO_PASSWORD로 통일)
- board_post: BOARD_POST_LIMIT개만 (지역/카테고리는 매핑표로 변환, 소프트삭제/비공개 제외)
- board_comment / board_post_like: 위에서 고른 게시글에 달린 것만 전부
- review: REVIEW_LIMIT개만 (place 테이블에 데이터가 있어야 함 - TourAPI 동기화나
  seed_dummy_places를 먼저 돌려야 함. 없으면 이 파트는 건너뜀)
- review_like: 위에서 고른 리뷰에 달린 것만 전부

반영 안 하는 것 (지금 스키마에 없어서): 대댓글, 리뷰 사진, oauth 로그인, 유저 프로필,
지역/카테고리 다국어명, 소프트삭제 이력. review_title은 review_comment 앞에 붙여서 content로 합침.
평점은 0.5 단위(1.5, 2.5 등)라 반올림해서 1~5 정수로 저장.
"""

import datetime
import math

import pandas as pd

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.models.place import Place
from app.models.board import BoardPost, BoardComment, BoardPostLike, BoardPostCompanion
from app.models.review import Review, ReviewLike
from app.services.score_service import recalculate_all_scores

USERS_XLSX = r"F:\K_trip\Data\output\users_en.xlsx"
BOARD_XLSX = r"F:\K_trip\Data\output\board_en.xlsx"
REVIEW_XLSX = r"F:\K_trip\Data\output\review_en.xlsx"

BOARD_POST_LIMIT = 10
REVIEW_LIMIT = 12

DEMO_PASSWORD = "ktrip-demo-1234"  # 이 계정들 전부 이 비밀번호로 로그인 가능

# board_regions region_id -> TourAPI area_code (경주는 광역 단위가 아니라 경북(35)으로 근사)
REGION_TO_AREA_CODE = {
    1: "1",    # 서울
    2: "6",    # 부산
    3: "39",   # 제주
    4: "35",   # 경주 -> 경북
    5: "32",   # 강원
    6: "38",   # 전남
    7: "2",    # 인천
    8: "31",   # 경기
    9: "4",    # 대구
    10: "5",   # 광주
}

# board_categories category_id -> BoardCategory 값
# (엑셀 카테고리엔 평점/장소 연결이 없어서 "review"로는 못 옮기고 전부 tips/qna로 매핑)
CATEGORY_TO_BOARD_CATEGORY = {
    1: "tips",       # travel_tip
    2: "tips",       # restaurant
    3: "tips",       # accommodation
    4: "tips",       # attraction (관광지 후기)
    5: "qna",        # question
}


# 엑셀 board_posts에는 REVIEW/COMPANION 타입이 아예 없어서(평점/장소연결/동행정보가
# 없는 구조 - CATEGORY_TO_BOARD_CATEGORY 위 주석 참고), 커뮤니티 화면의 네 탭이 전부
# 채워져 보이도록 손으로 만든 소량의 더미 게시글. place_id는 실제 place 테이블에서 순환 배정.
SYNTHETIC_REVIEW_POSTS = [
    {
        "title": "Three mornings at a Seoul market — what to actually order",
        "content": "I went three mornings in a row and tried something different each time. "
        "Crispy pancakes, mayak gimbap, and the yukhoe alley if you're brave. Go before 11am on weekdays.",
        "rating": 5,
        "area_code": "1",
    },
    {
        "title": "Sunrise hike was worth the 5am alarm",
        "content": "We hiked up in the dark with maybe forty other people and watched the sun come up "
        "over the crater rim. Bring a windbreaker even in summer — it's windy at the top.",
        "rating": 5,
        "area_code": "39",
    },
    {
        "title": "Go early, skip the crowds",
        "content": "Beautiful and genuinely fun to get lost in, but by 11am it's a queue. "
        "We arrived at 8:30 and had the place to ourselves.",
        "rating": 4,
        "area_code": "6",
    },
    {
        "title": "Underrated cafe street, way better than the famous one",
        "content": "Everyone talks about the same three streets, but this one had better coffee "
        "and a tenth of the crowd. Bring cash, some places don't take cards.",
        "rating": 4,
        "area_code": "1",
    },
]

SYNTHETIC_COMPANION_POSTS = [
    {
        "title": "Looking for 1-2 people: road trip, Oct 24-27",
        "content": "Renting a car for a 4-day loop. Splitting car + fuel + stays. "
        "I'm easygoing, planning relaxed mornings. DM if interested!",
        "destination": "Jeju",
        "start_date": datetime.date(2026, 10, 24),
        "end_date": datetime.date(2026, 10, 27),
        "travelers_needed": 4,
        "area_code": "39",
    },
    {
        "title": "Food crawl buddy, any weekend in November",
        "content": "Solo traveler, want a partner for a proper market crawl. "
        "I eat everything. Split everything, walk everywhere.",
        "destination": "Seoul",
        "start_date": None,
        "end_date": None,
        "travelers_needed": 2,
        "area_code": "1",
    },
    {
        "title": "3 days in Busan, looking for a travel buddy",
        "content": "First time in Korea, would love company for the beach + market days. "
        "No strict itinerary, happy to go with the flow.",
        "destination": "Busan",
        "start_date": datetime.date(2026, 11, 10),
        "end_date": datetime.date(2026, 11, 13),
        "travelers_needed": 3,
        "area_code": "6",
    },
    {
        "title": "Anyone else free for a Gyeongju history weekend?",
        "content": "Planning a slow weekend around the old tombs and temples. "
        "Looking for 1 more person to split a guesthouse.",
        "destination": "Gyeongju",
        "start_date": None,
        "end_date": None,
        "travelers_needed": 2,
        "area_code": "35",
    },
]


def to_datetime(value):
    """엑셀 셀 서식에 따라 문자열/Timestamp가 섞여 들어올 수 있어서 항상 datetime으로 변환"""
    return pd.to_datetime(value).to_pydatetime()


def round_rating(value: float) -> int:
    """0.5 단위 평점을 1~5 정수로 반올림 (반올림 규칙: 사사오입)"""
    rounded = math.floor(value + 0.5)
    return max(1, min(5, rounded))


def import_users(db) -> dict[int, int]:
    df = pd.read_excel(USERS_XLSX, sheet_name="users")
    excel_to_db_id: dict[int, int] = {}
    added = 0

    for _, row in df.iterrows():
        if pd.notna(row.get("deleted_at")):
            continue  # 탈퇴 처리된 더미 유저는 스킵

        existing = db.query(User).filter(User.email == row["email"]).first()
        if existing:
            excel_to_db_id[int(row["id"])] = existing.id
            continue

        user = User(
            email=row["email"],
            nickname=row["nickname"],
            hashed_password=hash_password(DEMO_PASSWORD),
            created_at=to_datetime(row["created_at"]),
        )
        db.add(user)
        db.flush()  # id 확보
        excel_to_db_id[int(row["id"])] = user.id
        added += 1

    db.commit()
    print(f"[users] {added}명 추가 (이미 있던 이메일은 건너뜀), 데모 비밀번호: {DEMO_PASSWORD}")
    return excel_to_db_id


def import_board(db, user_map: dict[int, int]) -> None:
    posts_df = pd.read_excel(BOARD_XLSX, sheet_name="board_posts")
    comments_df = pd.read_excel(BOARD_XLSX, sheet_name="board_comments")
    likes_df = pd.read_excel(BOARD_XLSX, sheet_name="board_post_likes")

    valid_posts = posts_df[(~posts_df["is_deleted"]) & (posts_df["is_public"])]
    chosen_posts = valid_posts.head(BOARD_POST_LIMIT)

    post_map: dict[int, int] = {}
    for _, row in chosen_posts.iterrows():
        user_id = user_map.get(int(row["user_id"]))
        if user_id is None:
            continue

        existing = (
            db.query(BoardPost)
            .filter(BoardPost.user_id == user_id, BoardPost.title == row["title"])
            .first()
        )
        if existing:
            post_map[int(row["post_id"])] = existing.id
            continue

        post = BoardPost(
            user_id=user_id,
            area_code=REGION_TO_AREA_CODE.get(int(row["region_id"])),
            category=CATEGORY_TO_BOARD_CATEGORY.get(int(row["category_id"]), "tips"),
            title=row["title"],
            content=row["content"],
            created_at=to_datetime(row["created_at"]),
        )
        db.add(post)
        db.flush()
        post_map[int(row["post_id"])] = post.id

    for _, row in comments_df.iterrows():
        if row["is_deleted"]:
            continue
        post_id = post_map.get(int(row["post_id"]))
        user_id = user_map.get(int(row["user_id"]))
        if post_id is None or user_id is None:
            continue  # 이번에 안 뽑힌 게시글의 댓글은 스킵

        existing = (
            db.query(BoardComment)
            .filter(
                BoardComment.post_id == post_id,
                BoardComment.user_id == user_id,
                BoardComment.content == row["content"],
            )
            .first()
        )
        if existing:
            continue

        db.add(
            BoardComment(
                post_id=post_id,
                user_id=user_id,
                content=row["content"],
                created_at=to_datetime(row["created_at"]),
            )
        )

    for _, row in likes_df.iterrows():
        post_id = post_map.get(int(row["post_id"]))
        user_id = user_map.get(int(row["user_id"]))
        if post_id is None or user_id is None:
            continue

        exists = (
            db.query(BoardPostLike)
            .filter(BoardPostLike.post_id == post_id, BoardPostLike.user_id == user_id)
            .first()
        )
        if exists:
            continue
        db.add(BoardPostLike(post_id=post_id, user_id=user_id))

    db.flush()

    # like_count/comment_count는 로컬 딕셔너리 대신 실제 DB 집계로 계산
    # (재실행해도 항상 정확한 값을 유지하기 위함)
    for db_post_id in post_map.values():
        post = db.query(BoardPost).filter(BoardPost.id == db_post_id).first()
        post.comment_count = (
            db.query(BoardComment).filter(BoardComment.post_id == db_post_id).count()
        )
        post.like_count = (
            db.query(BoardPostLike).filter(BoardPostLike.post_id == db_post_id).count()
        )

    db.commit()
    total_comments = db.query(BoardComment).filter(BoardComment.post_id.in_(post_map.values())).count()
    total_likes = db.query(BoardPostLike).filter(BoardPostLike.post_id.in_(post_map.values())).count()
    print(f"[board] 게시글 {len(post_map)}개 (누적 댓글 {total_comments}개, 좋아요 {total_likes}개)")


def import_reviews(db, user_map: dict[int, int]) -> None:
    place_ids = [p.id for p in db.query(Place.id).all()]
    if not place_ids:
        print("[review] place 테이블이 비어있어서 건너뜀 - TourAPI 동기화나 "
              "seed_dummy_places를 먼저 실행한 뒤 이 스크립트를 다시 돌리세요.")
        return

    reviews_df = pd.read_excel(REVIEW_XLSX, sheet_name="reviews")
    likes_df = pd.read_excel(REVIEW_XLSX, sheet_name="review_likes")

    valid_reviews = reviews_df[~reviews_df["is_deleted"]]
    chosen_reviews = valid_reviews.head(REVIEW_LIMIT)

    review_map: dict[int, int] = {}
    for _, row in chosen_reviews.iterrows():
        user_id = user_map.get(int(row["user_id"]))
        if user_id is None:
            continue

        # location_id <-> 실제 place_id는 대응 정보가 없어서 순환 배정
        place_id = place_ids[int(row["location_id"]) % len(place_ids)]
        content = f"{row['review_title']}\n\n{row['review_comment']}"

        existing = (
            db.query(Review)
            .filter(Review.user_id == user_id, Review.content == content)
            .first()
        )
        if existing:
            review_map[int(row["review_id"])] = existing.id
            continue

        review = Review(
            place_id=place_id,
            user_id=user_id,
            rating=round_rating(float(row["rating"])),
            content=content,
            created_at=to_datetime(row["created_at"]),
        )
        db.add(review)
        db.flush()
        review_map[int(row["review_id"])] = review.id

    like_count_by_review: dict[int, int] = {}
    for _, row in likes_df.iterrows():
        if row["is_deleted"]:
            continue
        review_id = review_map.get(int(row["review_id"]))
        user_id = user_map.get(int(row["user_id"]))
        if review_id is None or user_id is None:
            continue

        exists = (
            db.query(ReviewLike)
            .filter(ReviewLike.review_id == review_id, ReviewLike.user_id == user_id)
            .first()
        )
        if exists:
            continue
        db.add(ReviewLike(review_id=review_id, user_id=user_id))

    db.flush()

    # like_count는 로컬 딕셔너리 대신 실제 DB 집계로 계산 (재실행해도 항상 정확)
    for db_review_id in review_map.values():
        review = db.query(Review).filter(Review.id == db_review_id).first()
        review.like_count = (
            db.query(ReviewLike).filter(ReviewLike.review_id == db_review_id).count()
        )

    db.commit()
    recalculate_all_scores(db)
    total_likes = db.query(ReviewLike).count()
    print(f"[review] 리뷰 {len(review_map)}개 (누적 좋아요 {total_likes}개), place.score 재계산 완료")


def import_synthetic_posts(db, user_map: dict[int, int]) -> None:
    """REVIEW/COMPANION 타입 더미 게시글 (SYNTHETIC_REVIEW_POSTS/SYNTHETIC_COMPANION_POSTS 참고)"""
    user_ids = list(user_map.values())
    if not user_ids:
        print("[synthetic] 유저가 없어서 건너뜀")
        return

    place_ids = [p.id for p in db.query(Place.id).all()]

    added_review = 0
    if not place_ids:
        print("[synthetic] place 테이블이 비어있어서 REVIEW 타입 게시글은 건너뜀")
    else:
        for i, item in enumerate(SYNTHETIC_REVIEW_POSTS):
            user_id = user_ids[i % len(user_ids)]
            existing = (
                db.query(BoardPost)
                .filter(BoardPost.user_id == user_id, BoardPost.title == item["title"])
                .first()
            )
            if existing:
                continue

            db.add(
                BoardPost(
                    user_id=user_id,
                    area_code=item["area_code"],
                    category="review",
                    title=item["title"],
                    content=item["content"],
                    place_id=place_ids[i % len(place_ids)],
                    rating=item["rating"],
                )
            )
            added_review += 1

    added_companion = 0
    for i, item in enumerate(SYNTHETIC_COMPANION_POSTS):
        user_id = user_ids[(i + 1) % len(user_ids)]  # 리뷰랑 다른 유저로 살짝 겹치게
        existing = (
            db.query(BoardPost)
            .filter(BoardPost.user_id == user_id, BoardPost.title == item["title"])
            .first()
        )
        if existing:
            continue

        post = BoardPost(
            user_id=user_id,
            area_code=item["area_code"],
            category="companion",
            title=item["title"],
            content=item["content"],
        )
        db.add(post)
        db.flush()  # post.id 확보
        db.add(
            BoardPostCompanion(
                post_id=post.id,
                destination=item["destination"],
                start_date=item["start_date"],
                end_date=item["end_date"],
                travelers_needed=item["travelers_needed"],
            )
        )
        added_companion += 1

    db.commit()
    print(f"[synthetic] REVIEW 게시글 {added_review}개, COMPANION 게시글 {added_companion}개 추가")


def main():
    db = SessionLocal()
    try:
        user_map = import_users(db)
        import_board(db, user_map)
        import_reviews(db, user_map)
        import_synthetic_posts(db, user_map)
    finally:
        db.close()


if __name__ == "__main__":
    main()
