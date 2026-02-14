#!/bin/bash
# Hive Mind Hub Startup Script

echo "Starting Hive Mind Hub..."
echo "Database URL: ${DATABASE_URL:-Not set (will use SQLite)}"

# Run database initialization first
python -c "
from database import init_db
import sys
if init_db():
    print('Database initialized successfully')
    sys.exit(0)
else:
    print('Database initialization failed')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "Starting server..."
    uvicorn main:app --host 0.0.0.0 --port 8000
else
    echo "Failed to initialize database"
    exit 1
fi