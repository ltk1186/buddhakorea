# 완료 번역 공개 절차

번역 생성과 서비스 공개는 독립적이다. 아래 명령은 저장된 결과만 검증·반입하며 모델 API를 호출하지 않는다. DB와 웹 서버의 기존 운영 자원은 사용한다.

2026-09-22 법구경 최초 공개 완료. [실제 배포와 검증 기록](DHAMMAPADA_LIVE_RELEASE.md), `config/pali_publication_receipts.json`을 참고한다.

## 원칙

- 원문·번역 artifact와 SHA-256을 보존한다. 로컬 DB를 운영 DB에 덮어쓰거나 회원 데이터를 동기화하지 않는다.
- DB 스키마는 Alembic으로 맞춘다. 최초 공개는 revision 014까지 필요하다. 014는 후속 산문 문헌을 게송과 구별할 수 있게 한다.
- 반입은 하나의 트랜잭션이며 비공개 상태로 저장한다. 같은 release와 같은 파일을 다시 반입하면 unchanged이다. 다른 파일에는 새 release ID를 사용한다.
- 번역 교체는 같은 원문 집합에 새 release를 만든 뒤 공개 포인터를 전환한다. 원전 판본이나 구간 배치가 바뀌면 새 문헌 ID로 구분한다.
- 동일 문헌의 완료 번역을 다시 생성하지 않는다. `config/pali_translation_registry.json`과 완료 기록은 번역 실행 저장소에서 관리한다. 공개 DB의 `literature_publications`는 공개 상태이며 번역 완료 상태와 별개다.

## 운영 명령

승인된 artifact를 웹 공개 디렉터리 밖의 `/opt/buddha-korea/releases/translations/`에 전송하고 해당 파일의 hash를 로컬 영수증과 대조한다. 서버 `.env`는 GitHub Secrets로 관리하며 수동 수정하지 않는다.

```bash
cd /opt/buddha-korea
bash scripts/publish-translation.sh validate /absolute/artifact.json RELEASE SHA256 dhammapada
bash scripts/publish-translation.sh import /absolute/artifact.json RELEASE SHA256 dhammapada
bash scripts/publish-translation.sh status /absolute/artifact.json RELEASE SHA256 dhammapada
bash scripts/publish-translation.sh publish /absolute/artifact.json RELEASE SHA256 dhammapada
```

`dhammapada`는 검증된 최초 법구경 artifact의 엄격한 어댑터다. 후속 문헌은 마지막 인자로 `publication-v1`을 사용한다. CLI는 운영 Compose 네트워크의 `postgres/buddhakorea`에만 연결한다. 로컬 개발용 Python CLI는 기본 `--target local`로 루프백 PostgreSQL만 허용한다.

공개 후 비로그인으로 다음을 확인한다.

- `/pali/`의 문헌 목록과 `/pali/?lit=LITERATURE_ID`의 본문.
- `/api/v1/pali/literature/LITERATURE_ID/reading`의 release·구간 수·목차.
- 첫 장, 중간 장, 마지막 장, 부록, 직역·해설과 특정 구간 공유 링크.
- 공개 API의 전체 원문 및 번역 payload가 승인된 artifact와 일치하는지 대조.

콘텐츠 추가에는 프론트 수정이나 이미지 재빌드가 필요 없다. 공개 문헌 목록은 DB에서 불러온다. 새로운 계층 구조는 아래 package의 chapter/verse/kind 및 metadata로 매핑한다. 지금 제공하는 독서 UI는 문헌 → 장 → 구간의 두 단계 구조이며, 더 깊은 목차가 필요한 문헌에는 별도 UI 확장이 필요하다.

## 공개 취소·되돌리기

첫 공개를 취소하려면 같은 artifact/hash로 `unpublish`한다. 다른 release가 공개된 상태에서는 실수로 그 버전을 내리지 못하게 거부한다. 이전 번역으로 돌아가려면 보존된 이전 artifact/hash/release로 `publish`한다. DB 테이블을 삭제하거나 운영 DB 전체를 복원하지 않는다.

## 후속 문헌의 공통 package

```json
{
  "schema_version": "published_translation_v1",
  "literature": {
    "id": "unique-literature-id",
    "name": "한국어 제목",
    "pali_name": "Pali title",
    "pitaka": "sutta",
    "nikaya": "Khuddakanikāye",
    "display_metadata": {"description": "짧은 문헌 소개"}
  },
  "summary": {
    "count": 1,
    "source_commit": "pinned-source-commit",
    "model": "translation-model",
    "prompt_version": "translation-prompt-version"
  },
  "items": [{
    "source": {
      "literature_id": "unique-literature-id",
      "stable_segment_key": "stable-source-key",
      "sort_order": 1,
      "source_commit": "pinned-source-commit",
      "source_path": "romn/source.xml",
      "source_repo": "https://github.com/VipassanaTech/tipitaka-xml",
      "xml_node_path": "exact-XML-node-path",
      "vagga_name": "장 제목",
      "original_text": "원문",
      "normalized_text": "원문",
      "source_text_hash": "sha256-of-original-text"
    },
    "location": {"chapter": 1, "verse": null, "kind": "passage"},
    "result": {
      "stable_segment_key": "stable-source-key",
      "source_text_hash": "sha256-of-original-text",
      "status": "succeeded",
      "schema_valid": true,
      "parsed_translation_json": {
        "natural_ko": "번역",
        "literal_ko": "직역",
        "terms": [], "grammar_notes": [], "doctrinal_notes": [],
        "uncertainties": [], "quality_flags": []
      }
    }
  }]
}
```

위 예시는 구조 설명용이며 유효한 hash를 가진 실행 파일이 아니다. 전체 순서 1..count, 원문 hash, 번역 pairing, 성공 여부와 스키마를 검증한다. `chapter: null`은 부록, `verse`는 원전에 번호가 있는 게송, `kind`는 `verse/passage/supplement/appendix`다. source의 원전 식별 정보와 순서를 보존하며 편집으로 텍스트를 채워 넣지 않는다.

## 코드 배포와 데이터 배포의 분리

법구경 최초 공개 코드는 현재 운영 기준 commit `3d4ac3b`에서 분리한 `codex/publish-dhammapada`에 있다. 로컬 main의 별도 Gemini/RAG 개편을 함께 배포하지 않는다. 기존 main 자동 배포 workflow에는 유료 모델 smoke test가 있으므로 이 콘텐츠 공개에 사용하지 않는다. 추후 main으로 통합할 때에는 별도 모델 개편과 배포 검증 범위를 함께 검토해야 한다.

코드 배포 전 DB 백업을 임시 DB에 복원하여 migration과 콘텐츠 반입을 검증한다. 운영 변경 전에 기존 이미지 ID, git commit, frontend 백업과 DB dump를 기록한다. 이후 기존 Compose 구성으로 backend와 nginx만 교체하며 DB/Redis는 재생성하지 않는다. 모델 호출을 하는 채팅·검색·live preflight는 공개 검증에 사용하지 않는다.
