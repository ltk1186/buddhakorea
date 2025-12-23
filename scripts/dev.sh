#!/bin/bash
# ============================================================
# Buddha Korea - Development Environment Script
# ============================================================
# 사용법: ./scripts/dev.sh [command]
# Commands: start, stop, restart, logs, clean, db-reset
# ============================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/config/docker-compose.dev.yml"

# 함수: 로그 출력
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 함수: .env 파일 확인
check_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warn ".env 파일이 없습니다. .env.example을 복사합니다..."
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        log_warn ".env 파일을 수정하여 API 키를 설정해주세요."
    fi
}

# 함수: 필수 디렉토리 생성
create_dirs() {
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/chroma_db"
}

# 명령어: start
cmd_start() {
    log_info "개발 환경을 시작합니다..."
    check_env
    create_dirs

    docker-compose -f "$COMPOSE_FILE" up -d --build

    log_success "개발 환경이 시작되었습니다!"
    echo ""
    echo "  - Backend API:  http://localhost:8000"
    echo "  - API Docs:     http://localhost:8000/docs"
    echo "  - PostgreSQL:   localhost:5432"
    echo "  - Redis:        localhost:6379"
    echo ""
    log_info "로그 확인: ./scripts/dev.sh logs"
}

# 명령어: stop
cmd_stop() {
    log_info "개발 환경을 중지합니다..."
    docker-compose -f "$COMPOSE_FILE" down
    log_success "개발 환경이 중지되었습니다."
}

# 명령어: restart
cmd_restart() {
    cmd_stop
    cmd_start
}

# 명령어: logs
cmd_logs() {
    docker-compose -f "$COMPOSE_FILE" logs -f "${@:-backend}"
}

# 명령어: status
cmd_status() {
    docker-compose -f "$COMPOSE_FILE" ps
}

# 명령어: clean (볼륨까지 삭제)
cmd_clean() {
    log_warn "모든 개발 데이터를 삭제합니다. 계속하시겠습니까? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        docker-compose -f "$COMPOSE_FILE" down -v
        log_success "개발 데이터가 삭제되었습니다."
    else
        log_info "취소되었습니다."
    fi
}

# 명령어: db-reset (데이터베이스 초기화)
cmd_db_reset() {
    log_warn "PostgreSQL 데이터를 초기화합니다. 계속하시겠습니까? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        docker-compose -f "$COMPOSE_FILE" stop postgres
        docker volume rm buddhakorea_postgres-dev-data 2>/dev/null || true
        docker-compose -f "$COMPOSE_FILE" up -d postgres
        log_success "PostgreSQL이 초기화되었습니다."
    else
        log_info "취소되었습니다."
    fi
}

# 명령어: shell (backend 컨테이너에 접속)
cmd_shell() {
    docker-compose -f "$COMPOSE_FILE" exec backend bash
}

# 명령어: psql (PostgreSQL 접속)
cmd_psql() {
    docker-compose -f "$COMPOSE_FILE" exec postgres psql -U postgres -d buddhakorea
}

# 명령어: test
cmd_test() {
    docker-compose -f "$COMPOSE_FILE" exec backend pytest "${@:-tests/}"
}

# 메인
case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        shift
        cmd_logs "$@"
        ;;
    status)
        cmd_status
        ;;
    clean)
        cmd_clean
        ;;
    db-reset)
        cmd_db_reset
        ;;
    shell)
        cmd_shell
        ;;
    psql)
        cmd_psql
        ;;
    test)
        shift
        cmd_test "$@"
        ;;
    *)
        echo "Buddha Korea 개발 환경 스크립트"
        echo ""
        echo "사용법: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  start     개발 환경 시작 (Docker Compose)"
        echo "  stop      개발 환경 중지"
        echo "  restart   개발 환경 재시작"
        echo "  logs      로그 확인 (기본: backend)"
        echo "  status    컨테이너 상태 확인"
        echo "  clean     모든 개발 데이터 삭제"
        echo "  db-reset  PostgreSQL 초기화"
        echo "  shell     Backend 컨테이너 접속"
        echo "  psql      PostgreSQL CLI 접속"
        echo "  test      테스트 실행"
        echo ""
        ;;
esac
