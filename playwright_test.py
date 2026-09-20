"""
test_client.html의 모든 기능(회원가입~위치검색)을 실제 브라우저로 자동 클릭해보는
선택적(optional) 자동화 테스트. 필수는 아니고, 코드 바꾼 뒤 손으로 일일이 클릭 안 하고
빠르게 회귀 확인하고 싶을 때 사용.

사용법 (서버가 http://localhost:8000 에서 돌고 있어야 함):
    pip install playwright
    playwright install chromium
    python playwright_test.py
"""

import pathlib
from playwright.sync_api import sync_playwright

HTML_PATH = pathlib.Path(__file__).parent.joinpath("test_client.html").resolve().as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(HTML_PATH)

    def out(el_id):
        return page.locator(f"#{el_id}").inner_text()

    def click_button(name):
        page.get_by_role("button", name=name, exact=True).click()

    # 0) 연결 확인
    click_button("연결 확인")
    page.wait_for_timeout(500)
    print("=== health ===")
    print(out("healthOut"))
    assert "status" in out("healthOut")

    # 1) 회원가입
    click_button("회원가입")
    page.wait_for_timeout(500)
    print("=== signup ===")
    print(out("signupOut"))
    assert "[200]" in out("signupOut")

    # 2) 로그인
    click_button("로그인")
    page.wait_for_timeout(500)
    print("=== login ===")
    print(out("loginOut"))
    assert "[200]" in out("loginOut")
    token_display = out("tokenDisplay")
    print("token display:", token_display)
    assert "저장됨" in token_display

    # 3) AI 일정 추천
    click_button("일정 추천 받기")
    page.wait_for_timeout(500)
    print("=== itinerary ===")
    print(out("itineraryOut")[:500])
    assert "[200]" in out("itineraryOut")
    place_list_text = out("itPlaceList")
    print("place list:", place_list_text[:300])

    # 리스트에서 첫 장소 클릭 -> rvPlaceId 자동 입력되는지 확인
    page.click("#itPlaceList .place-item >> nth=0")
    filled_place_id = page.locator("#rvPlaceId").input_value()
    print("클릭으로 채워진 place_id:", filled_place_id)
    assert filled_place_id != ""

    # 4) 리뷰 작성 (로그인 되어 있어야 성공)
    click_button("리뷰 작성 (로그인 필요)")
    page.wait_for_timeout(500)
    print("=== review post ===")
    print(out("reviewOut"))
    assert "[200]" in out("reviewOut")

    # 리뷰 목록 조회
    click_button("리뷰 목록 조회")
    page.wait_for_timeout(500)
    print("=== review list ===")
    print(out("reviewOut"))
    assert "[200]" in out("reviewOut")

    # 좋아요 토글 (review_id=1 가정 - 방금 작성한 첫 리뷰)
    click_button("좋아요 토글 (로그인 필요)")
    page.wait_for_timeout(500)
    print("=== like toggle ===")
    print(out("reviewOut"))
    assert "[200]" in out("reviewOut")

    # 5) 게시판 글 작성
    click_button("글 작성 (로그인 필요)")
    page.wait_for_timeout(500)
    print("=== board post ===")
    print(out("boardOut"))
    assert "[200]" in out("boardOut")

    click_button("글 목록 조회")
    page.wait_for_timeout(500)
    print("=== board list ===")
    print(out("boardOut"))
    assert "[200]" in out("boardOut")

    # 댓글
    click_button("댓글 작성 (로그인 필요)")
    page.wait_for_timeout(500)
    print("=== comment post ===")
    print(out("commentOut"))
    assert "[200]" in out("commentOut")

    click_button("댓글 목록 조회")
    page.wait_for_timeout(500)
    print("=== comment list ===")
    print(out("commentOut"))
    assert "[200]" in out("commentOut")

    # 6) 위치기반 검색
    click_button("주변 관광지 검색")
    page.wait_for_timeout(500)
    print("=== nearby ===")
    print(out("nearbyOut")[:500])
    assert "[200]" in out("nearbyOut")
    print("nearby place list:", out("nearbyPlaceList")[:300])

    page.screenshot(path="/home/claude/k-trip-web-backend/demo_screenshot.png", full_page=True)

    browser.close()
    print()
    print("PLAYWRIGHT_E2E_ALL_PASSED")
