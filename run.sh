echo "🌿 Starting FolliageFusion..."

# Step 1: Create venv if it doesn't exist
if [ ! -d "venv" ]; then
  echo "🔧 Creating virtual environment..."
  python3 -m venv venv
fi

# Step 2: Activate it
source venv/bin/activate

# Step 3: Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Step 4: Run the main app
echo "🚀 Launching Flask servers..."
python main.py