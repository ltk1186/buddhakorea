# 법구경 라이브 공개 기록

공개일: 2026-09-22 (한국시간)

- 공개 주소: https://buddhakorea.com/pali/?lit=vri-romn-s0502m-mul
- 문헌 목록: https://buddhakorea.com/pali/
- 문헌 ID: `vri-romn-s0502m-mul`
- 공개 release: `dhp-ko-20260907-v22`
- 배포 코드: `1373020`, `codex/publish-dhammapada` (기존 운영 `3d4ac3b` 기준)
- DB revision: `014` (기존 `010`에서 순서대로 적용)
- 범위: 438구간 = 423개 번호 있는 게송 + 번호 없는 추가 게송 1개 + 권말 부속 글 14개. 26품과 권말 부록으로 제공.
- artifact SHA-256: `1ecf63ef1424474f390361049559c9786c44baa686bca6dfbe7834d4d2f84334`

## 공개와 비용

완료된 번역 파일을 그대로 반입했다. 원문·자연스러운 번역·직역·용어·해설을 새로 생성하거나 수정하지 않았다. 로그인 없이 읽으며, 독서 API는 DB 조회만 수행한다. 이번 배포·검증에서 번역/추론/임베딩 모델 API를 호출하지 않았다. 기존 VM·DB·트래픽 운영 비용과 향후 새 번역 생성 비용은 별개다.

## 검증 결과

- 로컬 PostgreSQL 읽기/반입 테스트 14개, 마이그레이션 회귀 테스트 7개 통과.
- 운영 DB를 백업하고 별도 DB에 복원한 후 010→014 적용, 반입·중복 반입·공개 확인.
- 복원 DB에서 438개 전체의 원문·번역 payload·해설 API를 artifact와 대조. 기존 47문헌/18,581구간 보존.
- 공개 도메인에서 438개 전체 원문·본문 번역과 목차 27개별 해설 표본을 대조.
- 홈→경전 읽기→법구경, 원문 표시, 직역·해설 펼치기, 모바일 390px 목차 전환과 마지막 품을 확인. 가로 넘침 없음.
- Backend, Nginx, PostgreSQL, Redis 모두 healthy. DB와 Redis 컨테이너는 재생성하지 않음.
- Cloudflare 경유 HTML 응답은 DYNAMIC이며 새 JS/CSS 해시와 공용 헤더 파일 정상 제공.

## 운영 위치와 복구

- 운영 저장소: `/opt/buddha-korea`
- 운영 artifact: `/opt/buddha-korea/releases/translations/dhp-ko-20260907-v22.json` (비공개 디렉터리)
- 공개 전 DB dump, 이전 git/image 식별자, frontend 백업: `/var/backups/buddhakorea/dhp-20260922/`
- 새 이미지: `config-backend:dhp-20260922`, `config-migrate:dhp-20260922`
- 이전 백엔드 이미지: `config-backend:before-dhp-20260922`

공개 취소는 [공통 공개 절차](PUBLISHING_TRANSLATIONS.md)의 `unpublish`를 사용한다. DB 전체 복원이나 테이블 삭제를 콘텐츠 공개 취소 용도로 사용하지 않는다. 이후 문헌도 검증→비공개 반입→공개 포인터 전환으로 추가한다. 현재 독서 UI는 문헌→장→구간 구조다.

## 다음 코드 배포 시 주의

이번에는 별도 Gemini/RAG 개편이 들어 있는 로컬 main 전체를 배포하지 않았다. 운영은 위 배포 브랜치를 사용한다. 기존 main 자동 배포는 모델 preflight/회귀 호출을 포함할 수 있으므로 콘텐츠 추가에 사용하지 않는다. 다음 코드 배포 전 이 공개 기능과 공용 헤더 변경을 main에 통합하고 마이그레이션/이미지 빌드를 확인해야 한다. 배포 브랜치를 오래된 main으로 덮어쓰면 읽기 기능이 사라질 수 있다.

새 문헌의 **번역 실행 승인**과 완료 기록은 `docs/PALI_TRANSLATION_STATUS.md`, `config/pali_translation_registry.json`을 별도로 따른다. 이번 공개는 자타카 유료 번역 실행 승인이 아니다.
