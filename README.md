# K-trip 웹 버전 백엔드

기존 AP_algorithm.py(엑셀 기반)를 TourAPI 4.0 기반으로 옮기고, 웹 버전에 필요한 백엔드
기능(AI 일정 추천 / 리뷰 / 게시판 / 위치기반 관광지 검색)을 이 FastAPI 프로젝트 하나로
통합했음. 프론트엔드와 실제 TourAPI 서비스키 연동만 빠져 있고, 그 외에는 sqlite로 전부
동작 검증까지 마친 상태.

## 아키텍처

기존 모바일 앱은 "Flutter → Spring Boot 메인 API(인증/CRUD) + 별도 Python AI 서버(추천 전담)"
구조였지만, **웹 버전은 이 FastAPI 프로젝트 하나로 전체 백엔드를 통합**하기로 함
(모바일 앱은 기존 Spring Boot 구조 그대로 유지). 그래서 리뷰·게시판 데이터도 이 프로젝트의
DB에 같이 있고, `score_service.py`도 외부 API 호출 없이 로컬 DB에서 바로 리뷰 통계를 가져옴.

## 폴더 구조

```
app/
  core/       설정(config.py), 인증 유틸(security.py - 비밀번호 해싱/JWT)
  external/   TourAPI 호출 클라이언트
  models/     SQLAlchemy 모델 (Place, ThemeMap, User, Review/ReviewLike, BoardPost/BoardComment 등)
  services/   비즈니스 로직 (테마 매핑, 점수제, 경로 계산, 일정 생성, 인증, 리뷰, 게시판, 위치검색)
  api/        FastAPI 라우터 (auth, itinerary, review, board, nearby)
  db/         DB 세션
alembic/               DB 마이그레이션 (버전 이력은 alembic/versions/)
schema.sql             현재 스키마를 SQL로만 보고 싶을 때 참고용 (alembic 마이그레이션과 항상 동기화)
provision_db.sql        DB/앱 전용 계정 최초 생성용 스크립트 (root로 1회 실행)
scripts/
  sync_tourapi.py         TourAPI -> DB 적재 배치
  seed_dummy_places.py    TourAPI 키 없이 테스트할 때 쓰는 더미 관광지 데이터 삽입
test_client.html          디자인 없는 기능 테스트용 웹페이지 (아래 설명)
playwright_test.py        (선택) test_client.html을 자동으로 클릭해보는 회귀 테스트
```

## 실행 순서

```bash
pip install -r requirements.txt

cp .env.example .env
# .env 열어서 TOUR_API_SERVICE_KEY, DATABASE_URL, JWT_SECRET_KEY 채우기
# (JWT_SECRET_KEY는 python -c "import secrets; print(secrets.token_hex(32))" 로 생성 추천)

# 0) DB 스키마 적용 (테이블 생성/변경은 Alembic이 담당함 - app 기동 시 자동 생성 안 함)
alembic upgrade head

# 1) TourAPI 데이터를 DB에 적재
python -m scripts.sync_tourapi

# 2) 서버 실행
uvicorn app.main:app --reload
```

모델(app/models/*.py)을 바꿨으면 서버 재시작 전에 새 마이그레이션을 만들고 적용해야 함:

```bash
alembic revision --autogenerate -m "설명"
alembic upgrade head
```

`http://localhost:8000/docs` 에서 Swagger로 전체 API 테스트 가능. 인증이 필요한 API는
`/auth/login`으로 토큰 받은 뒤 Swagger 우측 상단 Authorize에 `Bearer <토큰>` 형태로 입력.

## 디자인 없이 기능만 눈으로 확인해보고 싶을 때 (test_client.html)

프론트엔드가 아직 없어도 백엔드가 실제로 어떻게 동작하는지 화면으로 보고 싶다면:

```bash
# TourAPI 키가 아직 없으면 더미 데이터부터 채워넣기 (선택)
python -m scripts.seed_dummy_places

uvicorn app.main:app --reload
```

서버를 띄운 채로 `test_client.html` 파일을 그냥 더블클릭해서 브라우저로 열면 됨 (별도 설치나
서버 필요 없음). 회원가입 → 로그인 → 일정 추천 조회 → (추천 결과 목록에서 장소 클릭하면
리뷰란에 자동 입력) → 리뷰 작성/좋아요 → 게시판 글/댓글 → 위치기반 검색까지 버튼 누르면서
순서대로 테스트해볼 수 있음. 디자인은 전혀 안 잡혀있고 각 버튼 누르면 결과 JSON이 그대로
아래 회색 박스에 찍히는 정도라, 정말 "기능이 도는지"만 확인하는 용도임 - 프론트엔드 화면은
디자인 담당자가 이 API들을 그대로 호출해서 예쁘게 만들면 됨.

Base URL 입력칸이 있으니 서버를 다른 포트/주소로 띄웠으면 거기서 바꿔주면 됨. 실제로 Playwright
헤드리스 브라우저로 이 페이지의 모든 버튼을 순서대로 눌러보고 회원가입~위치검색까지 전부
200 응답 받는 것까지 확인해서 보내는 거니 바로 열어봐도 정상 동작할 거야.

`playwright_test.py`는 위 과정을 자동화한 선택적 회귀 테스트 스크립트임 (팀원 중 누군가 코드
바꾼 뒤 손으로 다 눌러보기 귀찮을 때 `python playwright_test.py`로 한 번에 확인 가능. 안 써도 무방).

## API 목록

| 기능 | 메서드/경로 | 인증 |
|---|---|---|
| 회원가입 | `POST /auth/signup` | X |
| 로그인 | `POST /auth/login` | X |
| AI 일정 추천 | `GET /itinerary?themes=food&themes=nature&days=3&places_per_day=5&area_code=1` (또는 프론트 이름 그대로 `categories=FOOD&region=SEOUL&pace=BALANCED`) | X |
| 관광지 목록 (Explore, 지역/카테고리 필터) | `GET /places?region=SEOUL&category=FOOD` (또는 `area_code=1&theme=food`) | X |
| 관광지 상세 조회 (평균 평점·리뷰 개수 포함) | `GET /places/{place_id}` | X |
| 리뷰 작성 | `POST /places/{place_id}/reviews` | O |
| 리뷰 목록 (특정 장소) | `GET /places/{place_id}/reviews` | X |
| 리뷰 전체 목록 (장소 무관) | `GET /reviews` | X |
| 리뷰 좋아요 토글 | `POST /reviews/{review_id}/like` | O |
| 게시글 작성 | `POST /board/posts` | O |
| 게시글 목록 (지역/카테고리 필터) | `GET /board/posts?area_code=1&category=qna` | X |
| 게시글 상세 | `GET /board/posts/{post_id}` | X |
| 게시글 좋아요 토글 | `POST /board/posts/{post_id}/like` | O |
| 댓글 작성 | `POST /board/posts/{post_id}/comments` | O |
| 댓글 목록 | `GET /board/posts/{post_id}/comments` | X |
| 댓글 좋아요 토글 | `POST /board/comments/{comment_id}/like` | O |
| 위치기반 주변 관광지 | `GET /places/nearby?lat=37.56&lon=126.97&radius_km=3` | X |

## 기능별 구현 메모

**AI 일정 추천** (23~27번 슬라이드 기준) — 테마 조합별 하루 구성(맛집만: 맛집3+관광지자동2,
맛집+기타: 맛집2+기타3), "점수×10 − 거리" 경로 공식, 맛집 연속 배치 방지, 숙소는 마지막 날
제외하고 매일 끝에 배치, 데이터 부족하면 빈 슬롯 유지 - 전부 반영 완료.

**프론트-백엔드 지역/카테고리 매핑** — 프론트(K-TRIP)는 지역명을 `SEOUL`/`BUSAN`처럼, 카테고리를
`FOOD`/`HALLYU`처럼 쓰는데 백엔드는 TourAPI 기준 `area_code`/`theme_code`를 쓰기 때문에,
`app/services/region_mapper.py`와 `theme_mapper.py`의 `FRONTEND_CATEGORY_TO_THEME`에 매핑표를
두고 `/itinerary`, `/places` API가 `region`/`categories` 파라미터로 프론트 이름을 그대로 받아서
내부적으로 변환하도록 만들어둠 (raw `area_code`/`theme`를 직접 넘기는 것도 계속 가능).
GANGNEUNG/GYEONGJU처럼 시/군 단위 지명은 광역 area_code로 근사한 것이라 완전히 정확하지는
않고, HALLYU 테마는 실제 데이터가 아직 없어서(위 한계 참고) 매핑은 돼 있어도 결과가 비어있을 수 있음.
같은 방식으로 `app/services/pace_mapper.py`에 프론트 Pace(RELAXED/BALANCED/PACKED) ->
`places_per_day`(3/5/7) 매핑도 있고, `/itinerary`가 `pace` 파라미터로 받음
(숫자는 임의로 정한 값이라 실사용해보고 팀에서 조정 가능).

**TourAPI 언어별 상품 주의** — TourAPI는 국문/영문 등 언어별로 서비스키가 따로 발급되고,
엔드포인트(`KorService2`/`EngService2`)도 그에 맞춰 바꿔야 함 (안 맞으면 403 Forbidden).
더 중요한 건 **contentTypeId 번호 체계 자체가 국문/영문 서비스마다 완전히 다르다**는 점
(예: 관광지가 국문은 12, 영문은 76) - `theme_mapper.py`의 `FOREIGN_CONTENT_TYPE_THEME`에
실제 EngService2 응답으로 확인한 값 기준으로 매핑해뒀음. 또한 영문 서비스의 "관광지"
분류 밑에는 병원/의원(의료관광) 데이터가 다수 섞여 있어서(cat1=A02 인문관광지 > cat2=A0202
웰니스관광 > cat3=A02020500 병원/의원), `sync_tourapi.py`가 이 cat3 코드만 정확히 걸러서
동기화 대상에서 제외함 (같은 cat2 밑의 공원·워터파크·크루즈 같은 정상 관광지는 유지).

**AI 기반 테마 재분류 (한류 등)** — TourAPI의 contentTypeId/cat1~3만으로는 "한류(hallyu)"를
전혀 구분 못 하는 근본적 한계가 있어서(theme_mapper.py 상단 설명), `scripts/label_themes_with_ai.py`로
Gemini(무료 티어)를 이용해 장소의 title/overview 텍스트를 보고 food/culture/hallyu/shopping/
sightseeing 중 하나로 재분류하는 배치 스크립트를 추가함. TourAPI 동기화 이후 한 번 실행하면 됨
(`python -m scripts.label_themes_with_ai`, `.env`의 `GEMINI_API_KEY` 필요 - 무료 발급:
https://aistudio.google.com/apikey). 비용 걱정 없이 무료 티어 안에서 끝내려고 장소를 25개씩
묶어서 요청하고(호출 횟수 최소화), 애초에 분류가 명확한 숙박/축제/레포츠/여행코스는 대상에서
빼서 꼭 필요한 것만 AI에 물어보게 만들어둠.

**Explore 관광지 목록/상세** — `GET /places`로 지역/카테고리 필터링된 목록(점수 높은 순)을,
`GET /places/{id}`로 상세(설명·전화번호 등)를 조회. 일정 추천처럼 알고리즘이 골라주는 게 아니라
있는 그대로 훑어보는 용도.

**리뷰** — 별점(1~5) + 좋아요(중복 방지 위해 ReviewLike 별도 테이블). 리뷰가 작성되거나
좋아요가 바뀌면 그 즉시 `score_service.refresh_place_score()`가 호출돼서 장소 점수와
추천 알고리즘에 바로 반영됨.

**게시판** — 응답에 `author_nickname`/`created_at`을 포함해서 프론트가 작성자명/작성일을 바로
표시할 수 있게 함 (원래 user_id만 있어서 프론트 연동 중 추가). 지역(area_code)별, 카테고리(Q&A/TIPS/REVIEW/COMPANION)별 글 작성·조회 + 댓글
(프론트엔드 K-TRIP 커뮤니티 화면 기준으로 맞춤 — 기존 PPT 초안의 날씨/양도/사담 카테고리는 뺐음).
REVIEW 타입은 특정 장소(place_id)에 대한 별점이 같이 달리고, COMPANION 타입은 동행 모집 정보
(목적지/기간/모집인원)가 별도 테이블(board_post_companion)에 붙음. 게시글/댓글 모두 좋아요
가능(review와 동일한 캐시 컬럼 + 중복방지 테이블 패턴).

**위치기반 관광지 검색(지도 기능)** — 지금은 sync_tourapi.py로 이미 적재해둔 자체 DB를
Haversine 거리로 계산해서 반환 (TourAPI 키 없이도 테스트 가능). "이건 API 사용 예정"이라고
했던 부분은, 나중에 실시간성이 필요하면 이미 만들어둔 `tourapi_client.fetch_location_based_list()`
(TourAPI의 locationBasedList2)로 교체하면 됨 - 그 경우 매 요청마다 외부 호출이 발생하니
캐싱/호출빈도 제한을 같이 고려할 것.

**인증** — JWT 방식 (PPT 11~12번 슬라이드에서 정한 이유 그대로: 웹+모바일 모두 지원, 서버가
상태를 안 들고 있어도 됨, 확장성). 비밀번호는 bcrypt로 해싱.

## 테스트 검증 상태

FastAPI `TestClient`로 sqlite 기준 아래 시나리오를 실제 HTTP 요청으로 통과 확인함:
회원가입/중복가입 차단/로그인/로그인 실패, 인증 없이 리뷰 작성 시도 시 차단,
리뷰 작성 후 점수 반영, 좋아요 토글(누르기/취소), 게시글 작성/잘못된 카테고리 차단/지역
필터링, 댓글 작성·조회, 위치기반 검색, 기존 AI 일정 추천 회귀 테스트까지 전부 통과.

## 아직 못 살린 부분

- **한류(hallyu) 테마**: TourAPI 분류 체계엔 "한류"라는 개념 자체가 없어서 content_type_id/cat1~3만
  으로는 구분이 안 됨. 키워드 매칭이나 기존 엑셀의 한류 장소 리스트를 살리는 방법을 정해야 함
  (`theme_mapper.py` 상단 설명 참고). "한류 음식슬롯/일반슬롯 분리" 규칙도 이게 정해져야 구현 가능
- `theme_mapper.py`의 `CAT1_THEME_OVERRIDE` - TourAPI `categoryCode2`로 실제 코드값 확인 후 채우기
  (자연/역사처럼 세분화된 테마가 필요하면 여기서 채워야 함)
- 실제 TourAPI 서비스키로 `sync_tourapi.py`를 한 번도 돌려본 적 없음 - 응답 필드명이 문서와 다를
  수 있어서 처음 실행 시 확인 필요
- 숙소 배치가 지금은 area_code 하나 기준 1곳 재사용으로 단순화되어 있음 (PPT 원본은 포괄 지역일
  때 여러 숙소 배치)
- 프론트엔드는 아직 미포함
- 운영 배포 전에는 `.env`의 `JWT_SECRET_KEY`를 반드시 랜덤값으로 바꿀 것 (기본값은 개발용 더미)
- CORS를 지금은 전체 허용(`allow_origins=["*"]`)으로 열어뒀음 - 실제 프론트엔드 도메인이 정해지면
  `app/main.py`에서 그 도메인만 허용하도록 좁힐 것
