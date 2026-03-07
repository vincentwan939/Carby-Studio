#!/bin/bash
# Carby Studio Prerequisites Check
# Verifies all required and optional dependencies

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Carby Studio Prerequisites Check"
echo "=========================================="
echo ""

# Track overall status
ALL_REQUIRED_MET=true
ANY_OPTIONAL_MET=false

# Required checks
echo -e "${BLUE}=== Required Dependencies ===${NC}"
echo ""

# Python 3.11+
check_python() {
    # Try to find Python 3.11+ in common locations
    PYTHON_CMD=""
    
    # Check various python commands
    for cmd in python3.12 python3.11 python3; do
        if command -v $cmd &> /dev/null; then
            PYTHON_VERSION=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
            MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
            
            if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 11 ]]; then
                PYTHON_CMD=$cmd
                break
            fi
        fi
    done
    
    # Also check Homebrew locations
    if [[ -z "$PYTHON_CMD" ]]; then
        for brew_python in /opt/homebrew/bin/python3.* /usr/local/bin/python3.*; do
            if [[ -x "$brew_python" ]]; then
                PYTHON_VERSION=$($brew_python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
                MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
                MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
                
                if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 11 ]]; then
                    PYTHON_CMD=$brew_python
                    break
                fi
            fi
        done
    fi
    
    if [[ -n "$PYTHON_CMD" ]]; then
        echo -e "${GREEN}✅ Python $PYTHON_VERSION found at $PYTHON_CMD (3.11+ required)${NC}"
        # Export for use by other checks
        export CARBY_PYTHON="$PYTHON_CMD"
        return 0
    else
        echo -e "${RED}❌ Python 3.11+ not found${NC}"
        echo "   Current: $(python3 --version 2>&1)"
        return 1
    fi
}

# Check fcntl module (Unix only)
check_fcntl() {
    if python3 -c "import fcntl" 2>/dev/null; then
        echo -e "${GREEN}✅ fcntl module (file locking)${NC}"
        return 0
    else
        echo -e "${RED}❌ fcntl module not available${NC}"
        echo "   Note: File locking requires Unix-like system (macOS/Linux)"
        return 1
    fi
}

# OpenClaw CLI
check_openclaw() {
    if command -v openclaw &> /dev/null; then
        echo -e "${GREEN}✅ OpenClaw CLI${NC}"
        return 0
    else
        echo -e "${RED}❌ OpenClaw CLI not found${NC}"
        return 1
    fi
}

# Git
check_git() {
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        echo -e "${GREEN}✅ Git $GIT_VERSION${NC}"
        return 0
    else
        echo -e "${RED}❌ Git not found${NC}"
        return 1
    fi
}

# Run required checks
REQUIRED_PASSED=0
REQUIRED_TOTAL=4

# Run checks but don't let them exit the script
set +e

if check_python; then ((REQUIRED_PASSED++)); else ALL_REQUIRED_MET=false; fi
if check_fcntl; then ((REQUIRED_PASSED++)); else ALL_REQUIRED_MET=false; fi
if check_openclaw; then ((REQUIRED_PASSED++)); else ALL_REQUIRED_MET=false; fi
if check_git; then ((REQUIRED_PASSED++)); else ALL_REQUIRED_MET=false; fi

set -e

echo ""
echo -e "${BLUE}Required: $REQUIRED_PASSED/$REQUIRED_TOTAL met${NC}"
echo ""

# Optional checks
echo -e "${BLUE}=== Optional Dependencies ===${NC}"
echo ""

# GitHub CLI
check_github() {
    if command -v gh &> /dev/null; then
        GH_VERSION=$(gh --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if gh auth status &> /dev/null; then
            echo -e "${GREEN}✅ GitHub CLI $GH_VERSION (authenticated)${NC}"
            ANY_OPTIONAL_MET=true
        else
            echo -e "${YELLOW}⚠️  GitHub CLI $GH_VERSION (not authenticated)${NC}"
            echo "   Run: gh auth login"
        fi
    else
        echo -e "${YELLOW}ℹ️  GitHub CLI (optional - install for GitHub integration)${NC}"
        echo "   Install: https://cli.github.com/"
    fi
}

# Docker
check_docker() {
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null; then
            DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
            echo -e "${GREEN}✅ Docker $DOCKER_VERSION (running)${NC}"
            ANY_OPTIONAL_MET=true
        else
            echo -e "${YELLOW}⚠️  Docker installed but not running${NC}"
            echo "   Start Docker Desktop or docker daemon"
        fi
    else
        echo -e "${YELLOW}ℹ️  Docker (optional - install for local deployment)${NC}"
        echo "   Install: https://docs.docker.com/get-docker/"
    fi
}

# Docker Compose
check_docker_compose() {
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        echo -e "${GREEN}✅ Docker Compose${NC}"
    else
        echo -e "${YELLOW}ℹ️  Docker Compose (optional - usually included with Docker Desktop)${NC}"
    fi
}

# Fly.io CLI
check_fly() {
    if command -v flyctl &> /dev/null; then
        FLY_VERSION=$(flyctl version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        echo -e "${GREEN}✅ Fly.io CLI $FLY_VERSION${NC}"
        ANY_OPTIONAL_MET=true
    else
        echo -e "${YELLOW}ℹ️  Fly.io CLI (optional - install for Fly deployment)${NC}"
        echo "   Install: https://fly.io/docs/hands-on/install-flyctl/"
    fi
}

check_github
check_docker
check_docker_compose
check_fly

echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""

if $ALL_REQUIRED_MET; then
    echo -e "${GREEN}✅ All required dependencies met!${NC}"
    echo "   Carby Studio is ready to use."
else
    echo -e "${RED}❌ Some required dependencies missing${NC}"
    echo "   Please install missing dependencies before using Carby Studio."
fi

echo ""

# Environment check
echo -e "${BLUE}=== Environment ===${NC}"
echo ""

if [[ -n "$CARBY_WORKSPACE" ]]; then
    echo -e "${GREEN}✅ CARBY_WORKSPACE=${CARBY_WORKSPACE}${NC}"
else
    echo -e "${YELLOW}ℹ️  CARBY_WORKSPACE not set (will use default: ~/.openclaw/workspace/projects)${NC}"
fi

# Check workspace directory
WORKSPACE="${CARBY_WORKSPACE:-$HOME/.openclaw/workspace/projects}"
if [[ -d "$WORKSPACE" ]]; then
    echo -e "${GREEN}✅ Workspace directory exists: $WORKSPACE${NC}"
else
    echo -e "${YELLOW}⚠️  Workspace directory will be created: $WORKSPACE${NC}"
fi

echo ""

# Next steps
if $ALL_REQUIRED_MET; then
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Create a project: carby-studio init my-app -g 'Build a REST API'"
    echo "  2. Check status: carby-studio status my-app"
    echo "  3. Run pipeline: carby-studio run my-app"
else
    echo -e "${YELLOW}Install missing dependencies:${NC}"
    
    if ! check_python &> /dev/null; then
        echo "  - Python 3.11+: brew install python@3.11 (macOS) or apt install python3.11 (Linux)"
    fi
    
    if ! check_openclaw &> /dev/null; then
        echo "  - OpenClaw: https://docs.openclaw.ai/installation"
    fi
    
    if ! check_git &> /dev/null; then
        echo "  - Git: brew install git (macOS) or apt install git (Linux)"
    fi
fi

echo ""

# Exit with appropriate code
if $ALL_REQUIRED_MET; then
    exit 0
else
    exit 1
fi
