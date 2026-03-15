#!/bin/bash
# First-time setup script for remote production server
# Run this once on a new server to configure environment
# Usage: ./setup_remote_server.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Remote Server Setup${NC}"
echo -e "${BLUE}======================================${NC}\n"

# Check if running on remote server
echo -e "${BLUE}Checking environment...${NC}"
if [ ! -d "${PROJECT_ROOT}/.git" ]; then
    echo -e "${RED}✗${NC} Error: Not in a git repository"
    echo "Please clone the repository first:"
    echo "  git clone <repository-url> /home/ubuntu/git/oscanner"
    exit 1
fi

# Create .env.local files from templates
echo -e "${BLUE}Setting up environment files...${NC}"

# Evaluator .env.local
if [ ! -f "${PROJECT_ROOT}/backend/evaluator/.env.local" ]; then
    if [ -f "${PROJECT_ROOT}/backend/evaluator/.env.local.template" ]; then
        cp "${PROJECT_ROOT}/backend/evaluator/.env.local.template" "${PROJECT_ROOT}/backend/evaluator/.env.local"
        echo -e "${GREEN}✓${NC} Created backend/evaluator/.env.local from template"
        echo -e "${YELLOW}⚠${NC} Please edit backend/evaluator/.env.local and add your API keys:"
        echo "  - OPEN_ROUTER_KEY (required)"
        echo "  - GITEE_TOKEN (required for Gitee repos)"
        echo "  - GITHUB_TOKEN (optional, for higher rate limits)"
    else
        echo -e "${RED}✗${NC} Template not found: backend/evaluator/.env.local.template"
    fi
else
    echo -e "${YELLOW}⚠${NC} backend/evaluator/.env.local already exists, skipping"
fi

# Webapp .env.local
if [ ! -f "${PROJECT_ROOT}/frontend/webapp/.env.local" ]; then
    if [ -f "${PROJECT_ROOT}/frontend/webapp/.env.local.template" ]; then
        cp "${PROJECT_ROOT}/frontend/webapp/.env.local.template" "${PROJECT_ROOT}/frontend/webapp/.env.local"
        echo -e "${GREEN}✓${NC} Created frontend/webapp/.env.local from template"
    else
        echo -e "${RED}✗${NC} Template not found: frontend/webapp/.env.local.template"
    fi
else
    echo -e "${YELLOW}⚠${NC} frontend/webapp/.env.local already exists, skipping"
fi

# Check for required tools
echo ""
echo -e "${BLUE}Checking required software...${NC}"

# Check Git
if command -v git >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Git is installed ($(git --version))"
else
    echo -e "${RED}✗${NC} Git is not installed"
    echo "  Install: sudo apt-get update && sudo apt-get install -y git"
fi

# Check Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js is installed ($NODE_VERSION)"

    # Check if version is >= 18
    MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$MAJOR_VERSION" -lt 18 ]; then
        echo -e "${YELLOW}⚠${NC} Warning: Node.js v18+ is recommended"
    fi
else
    echo -e "${RED}✗${NC} Node.js is not installed"
    echo "  Install: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
    echo "           sudo apt-get install -y nodejs"
fi

# Check npm
if command -v npm >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} npm is installed ($(npm --version))"
else
    echo -e "${RED}✗${NC} npm is not installed (should come with Node.js)"
fi

# uv will be auto-installed by start_production.sh
echo -e "${YELLOW}ℹ${NC} uv (Python package manager) will be auto-installed on first deployment"

# Make scripts executable
echo ""
echo -e "${BLUE}Setting script permissions...${NC}"
chmod +x "${PROJECT_ROOT}/start_production.sh"
chmod +x "${PROJECT_ROOT}/deploy.sh"
echo -e "${GREEN}✓${NC} Scripts are now executable"

# Summary
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}======================================${NC}\n"

echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Edit environment files with your API keys:"
echo "   ${BLUE}nano ${PROJECT_ROOT}/backend/evaluator/.env.local${NC}"
echo ""
echo "2. Deploy and start services:"
echo "   ${BLUE}./scripts/start_production.sh --daemon${NC}"
echo ""
echo "3. Or deploy from your local machine:"
echo "   ${BLUE}./scripts/deploy.sh${NC}"
echo ""

# Check if API keys are set
if [ -f "${PROJECT_ROOT}/backend/evaluator/.env.local" ]; then
    if grep -q "your-actual-key-here" "${PROJECT_ROOT}/backend/evaluator/.env.local" || \
       grep -q "your-actual-gitee-token-here" "${PROJECT_ROOT}/backend/evaluator/.env.local"; then
        echo -e "${RED}⚠ WARNING: Please update API keys in backend/evaluator/.env.local${NC}"
        echo "   Required: OPEN_ROUTER_KEY, GITEE_TOKEN"
    fi
fi
