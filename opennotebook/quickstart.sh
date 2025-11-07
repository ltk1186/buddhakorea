#!/bin/bash
# Quick Start Script for Buddhist AI Chatbot OpenNotebook Experiment

set -e  # Exit on error

echo "=========================================="
echo "Buddhist AI Chatbot - Quick Start"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Step 1: Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Step 2: Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Step 3: Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Step 4: Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - OPENAI_API_KEY or ANTHROPIC_API_KEY"
    echo ""
    read -p "Press Enter to continue after editing .env, or Ctrl+C to exit..."
else
    echo "✓ .env file found"
fi
echo ""

# Step 5: Check for sample data
if [ ! -f "data/processed/sample_metta_sutta.json" ]; then
    echo "⚠️  No sample data found"
else
    echo "✓ Sample data found"
fi
echo ""

# Step 6: Embed sample data
echo "📊 Would you like to embed the sample data? (y/n)"
read -p "> " embed_choice

if [ "$embed_choice" == "y" ]; then
    echo "🔄 Embedding sample data..."
    python scripts/embed_documents.py --input data/processed/ --batch-size 8
    echo "✓ Sample data embedded"
else
    echo "⏭️  Skipping embedding. You can run it later with:"
    echo "   python scripts/embed_documents.py --input data/processed/"
fi
echo ""

# Step 7: Start the server
echo "=========================================="
echo "✅ Setup complete!"
echo "=========================================="
echo ""
echo "To start the API server, run:"
echo "  uvicorn main:app --reload --port 8000"
echo ""
echo "Or with Docker:"
echo "  docker-compose up --build"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "To test the chat endpoint:"
echo "  curl -X POST http://localhost:8000/api/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"자애경(Metta Sutta)에 대해 설명해주세요\"}'"
echo ""
