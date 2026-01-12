#!/bin/bash
# Simple remote deployment script without systemd
# Uses screen sessions to run services in background

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load production config
source .env.production

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Simple Remote Deployment${NC}"
echo -e "${BLUE}======================================${NC}\n"
echo -e "Target: ${GREEN}${REMOTE_USER}@${REMOTE_HOST}${NC}"
echo -e "Evaluator Port: ${GREEN}${EVALUATOR_PORT}${NC}"
echo -e "Webapp Port: ${GREEN}${WEBAPP_PORT}${NC}\n"

# Test SSH connection
echo -e "${BLUE}[1/6] Testing SSH connection...${NC}"
if ssh -o ConnectTimeout=5 ${REMOTE_USER}@${REMOTE_HOST} "echo 'Connection OK'" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Connected"
else
    echo -e "${RED}✗${NC} Connection failed"
    exit 1
fi

# Create remote directory
echo -e "\n${BLUE}[2/6] Preparing remote directory...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_PATH}"
echo -e "${GREEN}✓${NC} Ready"

# Sync files
echo -e "\n${BLUE}[3/6] Syncing files...${NC}"
rsync -avz --progress \
    --exclude 'node_modules' \
    --exclude 'venv' \
    --exclude '.next' \
    --exclude '__pycache__' \
    --exclude '.git' \
    --exclude 'data' \
    --exclude 'cache' \
    --exclude 'evaluations' \
    --exclude '*.log' \
    ./ ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/
echo -e "${GREEN}✓${NC} Synced"

# Set up environment
echo -e "\n${BLUE}[4/6] Configuring environment...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cat > ${REMOTE_PATH}/evaluator/.env.production <<'EOF'
PORT=${EVALUATOR_PORT}
OPEN_ROUTER_KEY=$(grep OPEN_ROUTER_KEY evaluator/.env.local | cut -d'=' -f2)
GITEE_TOKEN=$(grep GITEE_TOKEN evaluator/.env.local | cut -d'=' -f2 | head -1)
PUBLIC_GITEE_TOKEN=$(grep PUBLIC_GITEE_TOKEN evaluator/.env.local | cut -d'=' -f2)
GITHUB_TOKEN=$(grep GITHUB_TOKEN evaluator/.env.local | cut -d'=' -f2)
EOF"

ssh ${REMOTE_USER}@${REMOTE_HOST} "cat > ${REMOTE_PATH}/webapp/.env.production.local <<'EOF'
PORT=${WEBAPP_PORT}
NEXT_PUBLIC_API_SERVER_URL=http://${REMOTE_HOST}:${EVALUATOR_PORT}
EOF"
echo -e "${GREEN}✓${NC} Environment configured"

# Install dependencies
echo -e "\n${BLUE}[5/6] Installing dependencies...${NC}"
echo "  - Python packages..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH}/evaluator && \
    python3 -m venv venv && \
    source venv/bin/activate && \
    pip install -q --upgrade pip && \
    pip install -q -r requirements.txt"

echo "  - Node.js packages and building webapp..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "
    export NVM_DIR=\"\$HOME/.nvm\"
    [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\"
    cd ${REMOTE_PATH}/webapp && \
    npm install --silent && \
    npm run build"
echo -e "${GREEN}✓${NC} Dependencies installed"

# Stop existing services
echo -e "\n${BLUE}[6/6] Starting services...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "
    # Kill existing screen sessions
    screen -S evaluator -X quit 2>/dev/null || true
    screen -S webapp -X quit 2>/dev/null || true
    sleep 2

    # Start evaluator in screen
    cd ${REMOTE_PATH}/evaluator
    source venv/bin/activate
    source .env.production
    screen -dmS evaluator bash -c 'PORT=${EVALUATOR_PORT} python server.py > ../evaluator.log 2>&1'
    sleep 3

    # Start webapp in screen
    cd ${REMOTE_PATH}/webapp
    export NVM_DIR=\"\$HOME/.nvm\"
    [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\"
    screen -dmS webapp bash -c 'export NVM_DIR=\"\$HOME/.nvm\"; [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\"; PORT=${WEBAPP_PORT} npm start > ../webapp.log 2>&1'
    sleep 2

    # Show screen sessions
    screen -ls
"
echo -e "${GREEN}✓${NC} Services started in screen sessions"

echo -e "\n${BLUE}======================================${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${BLUE}======================================${NC}\n"

echo -e "${BLUE}Access URLs:${NC}"
echo -e "  Evaluator API: ${GREEN}http://${REMOTE_HOST}:${EVALUATOR_PORT}${NC}"
echo -e "  Webapp:        ${GREEN}http://${REMOTE_HOST}:${WEBAPP_PORT}${NC}"
echo -e "  API Docs:      ${GREEN}http://${REMOTE_HOST}:${EVALUATOR_PORT}/docs${NC}"

echo -e "\n${BLUE}Management Commands:${NC}"
echo -e "  View logs:           ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'tail -f ${REMOTE_PATH}/*.log'${NC}"
echo -e "  Attach to evaluator: ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} -t 'screen -r evaluator'${NC}"
echo -e "  Attach to webapp:    ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} -t 'screen -r webapp'${NC}"
echo -e "  List sessions:       ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'screen -ls'${NC}"
echo -e "  Restart:             ${YELLOW}./deploy_simple.sh${NC}"
