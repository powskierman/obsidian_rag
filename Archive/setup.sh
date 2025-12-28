#!/bin/bash
# Obsidian RAG Setup Script
# Makes it easy for users to get started

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          🧠 Obsidian RAG - Initial Setup                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_check() { echo -e "${GREEN}✅ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Step 1: Check Python
echo "Step 1: Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_check "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.10 or higher."
    exit 1
fi

# Step 2: Check if pip is available
echo ""
echo "Step 2: Checking pip..."
if python3 -m pip --version &> /dev/null; then
    PIP_VERSION=$(python3 -m pip --version)
    print_check "pip found: $PIP_VERSION"
else
    print_error "pip not found. Please install pip."
    exit 1
fi

# Step 3: Create .env.local if it doesn't exist
echo ""
echo "Step 3: Setting up environment variables..."
if [ -f .env.local ]; then
    print_warn ".env.local already exists. Skipping creation."
else
    cat > .env.local << 'EOF'
# Anthropic API Configuration
# Get your key from: https://console.anthropic.com/account/keys
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b

# Embedding Model
EMBED_MODEL=nomic-embed-text

# Optional: Adjust these if needed
DEBUG=false
LOG_LEVEL=INFO
EOF
    print_check ".env.local created"
    print_warn "⚠️  IMPORTANT: Edit .env.local and add your Anthropic API key!"
    echo ""
    read -p "Would you like to edit .env.local now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env.local
    fi
fi

# Step 4: Install Python dependencies
echo ""
echo "Step 4: Installing Python dependencies..."
if python3 -m pip install -r requirements.txt -q; then
    print_check "Dependencies installed"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Step 5: Check for optional dependencies
echo ""
echo "Step 5: Checking for optional dependencies..."
if python3 -c "import torch" 2>/dev/null; then
    print_check "PyTorch already installed"
else
    print_warn "PyTorch not found. Installing (this may take a while)..."
    python3 -m pip install torch -q
fi

# Step 6: Check for Docker (optional but recommended)
echo ""
echo "Step 6: Checking for Docker (optional)..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_check "Docker found: $DOCKER_VERSION"
    DOCKER_AVAILABLE=true
else
    print_warn "Docker not found. You can still run locally, but Docker is recommended."
    DOCKER_AVAILABLE=false
fi

# Step 7: Check for Ollama
echo ""
echo "Step 7: Checking for Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_check "Ollama is running"
    OLLAMA_RUNNING=true
else
    print_warn "Ollama is not running or not accessible"
    echo "   To start Ollama, run: ollama serve"
    echo "   Or download from: https://ollama.ai"
    OLLAMA_RUNNING=false
fi

# Step 8: Summary and next steps
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Setup Complete!                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Next Steps:"
echo ""

if [ ! -s .env.local ] || grep -q "your-api-key-here" .env.local; then
    echo "1️⃣  Edit .env.local and add your Anthropic API key"
    echo "   ${BLUE}nano .env.local${NC}"
    echo ""
fi

if [ "$OLLAMA_RUNNING" = false ]; then
    echo "2️⃣  Start Ollama in a terminal:"
    echo "   ${BLUE}ollama serve${NC}"
    echo "   (or ${BLUE}ollama pull qwen2.5-coder:14b${NC} to download the model)"
    echo ""
fi

if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "3️⃣  Start Obsidian RAG with Docker (Recommended):"
    echo "   ${BLUE}./Scripts/docker_start.sh${NC}"
    echo ""
    echo "   OR run locally:"
    echo "   ${BLUE}./run.sh${NC}"
else
    echo "3️⃣  Start Obsidian RAG:"
    echo "   ${BLUE}./run.sh${NC}"
fi

echo ""
echo "🌐 Then access the UI at: http://localhost:8501"
echo ""
echo "📚 Learn more:"
echo "   - Quick Start: ./QUICKSTART.md"
echo "   - Documentation: ./Documentation/README.md"
echo "   - Troubleshooting: ./Documentation/TROUBLESHOOTING.md"
echo ""
