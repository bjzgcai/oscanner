#!/bin/bash
# Remote deployment script for Engineer Skill Evaluator
# Deploys to remote servers with one command
# Usage: ./deploy.sh [--rebuild]

set -e

# Load configuration from .env.production
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.production"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env.production file not found"
    echo "Please create .env.production with REMOTE_HOST, REMOTE_USER, and REMOTE_PATH"
    exit 1
fi

# Load environment variables
export $(cat "$ENV_FILE" | grep -v '^#' | grep -v '^$' | xargs)

# Validate required variables
if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_USER" ] || [ -z "$REMOTE_PATH" ]; then
    echo "Error: Missing required variables in .env.production"
    echo "Required: REMOTE_HOST, REMOTE_USER, REMOTE_PATH"
    exit 1
fi

# Parse arguments
REBUILD_FLAG=""
if [ "$1" = "--rebuild" ]; then
    REBUILD_FLAG="--rebuild"
fi

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Deploying to Remote Server${NC}"
echo -e "${BLUE}======================================${NC}\n"
echo -e "  Host: ${GREEN}${REMOTE_HOST}${NC}"
echo -e "  User: ${GREEN}${REMOTE_USER}${NC}"
echo -e "  Path: ${GREEN}${REMOTE_PATH}${NC}\n"

# Deploy to remote server
ssh ${REMOTE_USER}@${REMOTE_HOST} << ENDSSH
    set -e

    echo -e "${BLUE}Navigating to project directory...${NC}"
    cd "${REMOTE_PATH}"

    echo -e "${BLUE}Fetching latest changes...${NC}"
    git fetch origin
    git reset --hard origin/main

    echo -e "${BLUE}Starting/restarting services...${NC}"
    chmod +x start_production.sh
    ./start_production.sh ${REBUILD_FLAG} --daemon

    echo -e "${GREEN}✓ Deployment completed successfully${NC}"
ENDSSH

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Services are now running on ${REMOTE_HOST}"
echo "  Evaluator: http://${REMOTE_HOST}:${EVALUATOR_PORT:-8001}"
echo "  Webapp:    http://${REMOTE_HOST}:${WEBAPP_PORT:-3001}"
echo ""
echo "To view logs:"
echo "  ssh ${REMOTE_USER}@${REMOTE_HOST} 'tail -f ${REMOTE_PATH}/evaluator.log ${REMOTE_PATH}/webapp.log'"
echo ""
echo "To stop services:"
echo "  ssh ${REMOTE_USER}@${REMOTE_HOST} \"pkill -f 'oscanner serve|next start'\""
