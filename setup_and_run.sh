#!/bin/bash

# --- Color Definitions ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 서울시 청년정책 GraphRAG 통합 설정 및 실행 스크립트 시작${NC}"

# 1. 필수 도구 확인
echo -e "\n${YELLOW}[1/6] 필수 도구 확인 중...${NC}"
if ! command -v uv &> /dev/null; then echo -e "${RED}❌ uv가 설치되어 있지 않습니다. (https://astral.sh/uv)${NC}"; exit 1; fi
if ! command -v docker &> /dev/null; then echo -e "${RED}❌ docker가 설치되어 있지 않습니다.${NC}"; exit 1; fi
echo -e "✅ uv 및 docker 확인 완료."

# 2. .env 파일 설정
echo -e "\n${YELLOW}[2/6] 환경 변수(.env) 설정 확인 중...${NC}"
if [ ! -f .env ]; then
    echo -e "⚠️  .env 파일이 없습니다. 템플릿을 생성합니다."
    echo "OPENAI_API_KEY=your_key_here" > .env
    echo "NEO4J_URI=bolt://localhost:7687" >> .env
    echo "NEO4J_USERNAME=neo4j" >> .env
    echo "NEO4J_PASSWORD=testpassword" >> .env
    echo -e "${RED}❌ .env 파일에 OPENAI_API_KEY를 입력한 후 다시 실행해주세요.${NC}"
    exit 1
fi
echo -e "✅ .env 설정 확인 완료."

# 3. Neo4j Docker 컨테이너 실행
echo -e "\n${YELLOW}[3/6] Neo4j 도커 컨테이너 상태 확인...${NC}"
if [ "$(docker ps -aq -f name=neo4j-hackerton)" ]; then
    if [ ! "$(docker ps -q -f name=neo4j-hackerton)" ]; then
        echo " > 중지된 컨테이너를 시작합니다..."
        docker start neo4j-hackerton
    else
        echo " > 컨테이너가 이미 실행 중입니다."
    fi
else
    echo " > 새 컨테이너를 생성하고 실행합니다..."
    docker run \
        --name neo4j-hackerton \
        -p 7474:7474 -p 7687:7687 \
        -d \
        -e NEO4J_AUTH=neo4j/testpassword \
        -e NEO4J_PLUGINS='["apoc"]' \
        neo4j:5.26.0
fi

# 4. Neo4j 부팅 대기
echo -e "\n${YELLOW}[4/6] Neo4j 서비스 준비 대기 중 (최대 60초)...${NC}"
MAX_RETRIES=30
COUNT=0
until uv run python3 -c "import socket; s = socket.socket(); s.connect(('localhost', 7687))" &> /dev/null; do
    echo -n "."
    sleep 2
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n${RED}❌ Neo4j 부팅 시간이 초과되었습니다. 도커 로그를 확인하세요.${NC}"
        exit 1
    fi
done
echo -e "\n✅ Neo4j 준비 완료."

# 5. 의존성 설치 및 데이터 구축
echo -e "\n${YELLOW}[5/6] 라이브러리 설치 및 지식 그래프 구축...${NC}"
uv sync

echo -e "\n${GREEN}🏗️  Step 1: 공문서 기초 데이터 구축 (301)${NC}"
uv run graph_db/301_build_real_graph.py

echo -e "\n${GREEN}🏗️  Step 2: 공문서 본문 임베딩 및 인덱스 생성 (302)${NC}"
uv run graph_db/302_update_doc_content.py

echo -e "\n${GREEN}🏗️  Step 3: 민원 데이터 추가 및 유사도 연결 (303)${NC}"
uv run graph_db/303_add_complaints_node.py

# 6. 서버 실행
echo -e "\n${YELLOW}[6/6] 모든 준비가 완료되었습니다. API 서버를 실행합니다!${NC}"
echo -e "${GREEN}🌐 대시보드 접속: http://localhost:8000${NC}"
echo -e "${YELLOW}중단하려면 Ctrl+C를 누르세요.${NC}\n"

uv run uvicorn graph_db.api_server_real:app --host 0.0.0.0 --port 8000 --reload
