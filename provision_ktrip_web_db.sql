-- 예전 모바일 앱 시절 데이터(ktrip DB)와 분리하기 위한 새 DB 생성.
-- root로 한 번만 실행하면 됩니다. 기존 ktrip_app 계정을 그대로 재사용해서
-- 새 비밀번호를 또 만들 필요는 없습니다 - 이 DB에 대한 권한만 추가로 부여합니다.

CREATE DATABASE IF NOT EXISTS ktrip_web
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP
    ON ktrip_web.* TO 'ktrip_app'@'localhost';

FLUSH PRIVILEGES;
