# ============================================================
# Buddha Korea - Makefile
# ============================================================
# 사용법: make <command>
# ============================================================

.PHONY: help dev dev-stop dev-logs dev-clean test lint format build deploy

# Default
help:
	@echo "Buddha Korea 개발 명령어"
	@echo ""
	@echo "개발 환경 (Docker):"
	@echo "  make dev          개발 서버 시작 (Frontend + Backend + DB)"
	@echo "  make dev-stop     개발 서버 중지"
	@echo "  make dev-logs     로그 확인"
	@echo "  make dev-clean    개발 데이터 초기화"
	@echo ""
	@echo "코드 품질:"
	@echo "  make test         테스트 실행"
	@echo "  make lint         린트 검사"
	@echo "  make format       코드 포맷팅"
	@echo ""
	@echo "프로덕션:"
	@echo "  make build        프로덕션 이미지 빌드"
	@echo "  make deploy       프로덕션 배포"
	@echo ""

# ──────────────────────────────────────────────────────────
# Development (Docker)
# ──────────────────────────────────────────────────────────
dev:
	@./scripts/dev.sh start

dev-stop:
	@./scripts/dev.sh stop

dev-restart:
	@./scripts/dev.sh restart

dev-logs:
	@./scripts/dev.sh logs

dev-status:
	@./scripts/dev.sh status

dev-clean:
	@./scripts/dev.sh clean

dev-shell:
	@./scripts/dev.sh shell

dev-psql:
	@./scripts/dev.sh psql

# ──────────────────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────────────────
test:
	@./scripts/dev.sh test

test-cov:
	@docker-compose -f config/docker-compose.dev.yml exec backend \
		pytest tests/ --cov=backend --cov-report=html

# ──────────────────────────────────────────────────────────
# Code Quality
# ──────────────────────────────────────────────────────────
lint:
	@docker-compose -f config/docker-compose.dev.yml exec backend \
		ruff check backend/ tests/

format:
	@docker-compose -f config/docker-compose.dev.yml exec backend \
		ruff format backend/ tests/

# ──────────────────────────────────────────────────────────
# Production
# ──────────────────────────────────────────────────────────
build:
	docker build -t buddhakorea:latest .

deploy:
	@echo "프로덕션 배포는 config/docker-compose.yml 사용"
	docker-compose -f config/docker-compose.yml up -d --build

deploy-stop:
	docker-compose -f config/docker-compose.yml down

# ──────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────
setup:
	@echo "개발 환경 초기 설정..."
	@test -f .env || cp .env.example .env
	@mkdir -p logs chroma_db
	@echo "완료! .env 파일에서 API 키를 설정해주세요."

clean-all:
	@echo "모든 Docker 리소스 정리..."
	docker-compose -f config/docker-compose.dev.yml down -v --rmi local
	docker-compose -f config/docker-compose.yml down -v --rmi local
