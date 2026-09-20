-- ktrip DB + 앱 전용 계정 생성 스크립트
-- root로 한 번만 실행하면 됩니다. (비밀번호는 본인이 CHANGE_ME 자리에 직접 채워서 실행하세요)
--
-- 실행 전에 아래 'CHANGE_ME_STRONG_PASSWORD' 부분을 원하는 비밀번호로 바꿔주세요.
-- 이 비밀번호를 나중에 .env의 DATABASE_URL에도 그대로 넣어야 합니다.

CREATE DATABASE IF NOT EXISTS ktrip
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 앱은 root가 아니라 이 전용 계정으로 접속하게 됩니다 (운영 보안 기본 원칙).
CREATE USER IF NOT EXISTS 'ktrip_app'@'localhost' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

-- ktrip DB에 대해서만 필요한 권한만 부여 (다른 DB는 접근 불가)
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP
    ON ktrip.* TO 'ktrip_app'@'localhost';

FLUSH PRIVILEGES;
