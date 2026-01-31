#!/bin/bash
# Remote deployment script for Engineer Skill Evaluator
# Deploys to remote server with configurable ports

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
echo -e "${BLUE}  Remote Deployment${NC}"
echo -e "${BLUE}======================================${NC}\n"
echo -e "Target: ${GREEN}${REMOTE_USER}@${REMOTE_HOST}${NC}"
echo -e "Evaluator Port: ${GREEN}${EVALUATOR_PORT}${NC}"
echo -e "Webapp Port: ${GREEN}${WEBAPP_PORT}${NC}"
echo -e "Remote Path: ${GREEN}${REMOTE_PATH}${NC}\n"

# Check SSH connection
echo -e "${BLUE}[1/7] Testing SSH connection...${NC}"
if ssh -o ConnectTimeout=5 ${REMOTE_USER}@${REMOTE_HOST} "echo 'SSH connection successful'" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} SSH connection successful"
else
    echo -e "${RED}✗${NC} SSH connection failed. Please check your SSH key setup."
    exit 1
fi

# Create remote directory
echo -e "\n${BLUE}[2/7] Creating remote directory...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_PATH}"
echo -e "${GREEN}✓${NC} Remote directory ready"

# Sync project files (excluding large directories)
echo -e "\n${BLUE}[3/7] Syncing project files...${NC}"
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
echo -e "${GREEN}✓${NC} Files synced"

# Create production environment files on remote
echo -e "\n${BLUE}[4/7] Setting up environment files...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cat > ${REMOTE_PATH}/backend/evaluator/.env.production <<'EOF'
PORT=${EVALUATOR_PORT}
OPEN_ROUTER_KEY=$(grep OPEN_ROUTER_KEY backend/evaluator/.env.local | cut -d'=' -f2)
GITEE_TOKEN=$(grep GITEE_TOKEN backend/evaluator/.env.local | cut -d'=' -f2 | head -1)
GITHUB_TOKEN=$(grep GITHUB_TOKEN backend/evaluator/.env.local | cut -d'=' -f2)
EOF"

ssh ${REMOTE_USER}@${REMOTE_HOST} "cat > ${REMOTE_PATH}/frontend/webapp/.env.production.local <<'EOF'
PORT=${WEBAPP_PORT}
NEXT_PUBLIC_API_SERVER_URL=http://${REMOTE_HOST}:${EVALUATOR_PORT}
EOF"
echo -e "${GREEN}✓${NC} Environment files created"

# Set up Python virtual environment and install dependencies
echo -e "\n${BLUE}[5/7] Setting up Python environment...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH}/backend/evaluator && \
    python3 -m venv venv && \
    source venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt"
echo -e "${GREEN}✓${NC} Python environment ready"

# Install Node.js dependencies and build webapp
echo -e "\n${BLUE}[6/7] Building webapp...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH}/frontend/webapp && \
    export NVM_DIR=\"\$HOME/.nvm\" && \
    [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && \
    nvm install 20 && \
    nvm use 20 && \
    npm install && \
    npm run build"
echo -e "${GREEN}✓${NC} Webapp built"

# Create systemd service files for production deployment
echo -e "\n${BLUE}[7/7] Setting up production services...${NC}"

# Create evaluator service
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo tee /etc/systemd/system/evaluator.service > /dev/null <<'EOF'
[Unit]
Description=Engineer Skill Evaluator API
After=network.target

[Service]
Type=simple
User=${REMOTE_USER}
WorkingDirectory=${REMOTE_PATH}/backend/evaluator
Environment=\"PATH=${REMOTE_PATH}/backend/evaluator/venv/bin\"
EnvironmentFile=${REMOTE_PATH}/backend/evaluator/.env.production
ExecStart=${REMOTE_PATH}/backend/evaluator/venv/bin/python ${REMOTE_PATH}/backend/evaluator/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

# Create webapp service
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo tee /etc/systemd/system/webapp.service > /dev/null <<'EOF'
[Unit]
Description=Engineer Skill Evaluator Webapp
After=network.target evaluator.service

[Service]
Type=simple
User=${REMOTE_USER}
WorkingDirectory=${REMOTE_PATH}/frontend/webapp
EnvironmentFile=${REMOTE_PATH}/frontend/webapp/.env.production.local
ExecStart=/bin/bash -c 'export NVM_DIR=\"\$HOME/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm use 20 && npm start'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

# Reload systemd and start services
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo systemctl daemon-reload && \
    sudo systemctl enable evaluator webapp && \
    sudo systemctl restart evaluator && \
    sleep 3 && \
    sudo systemctl restart webapp"

echo -e "${GREEN}✓${NC} Services configured and started"

# Check service status
echo -e "\n${BLUE}======================================${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${BLUE}======================================${NC}\n"

echo -e "Service Status:"
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo systemctl status evaluator --no-pager -l | head -n 5"
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo systemctl status webapp --no-pager -l | head -n 5"

echo -e "\n${BLUE}Access URLs:${NC}"
echo -e "  Evaluator API: ${GREEN}http://${REMOTE_HOST}:${EVALUATOR_PORT}${NC}"
echo -e "  Webapp:        ${GREEN}http://${REMOTE_HOST}:${WEBAPP_PORT}${NC}"
echo -e "  API Docs:      ${GREEN}http://${REMOTE_HOST}:${EVALUATOR_PORT}/docs${NC}"

echo -e "\n${BLUE}Useful Commands:${NC}"
echo -e "  View evaluator logs:  ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'sudo journalctl -u evaluator -f'${NC}"
echo -e "  View webapp logs:     ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'sudo journalctl -u webapp -f'${NC}"
echo -e "  Restart services:     ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'sudo systemctl restart evaluator webapp'${NC}"
echo -e "  Stop services:        ${YELLOW}ssh ${REMOTE_USER}@${REMOTE_HOST} 'sudo systemctl stop evaluator webapp'${NC}"
