#!/bin/bash

# Load .env file and export variables
if [ -f .env ]; then
  while IFS='=' read -r key value; do
    # Remove leading/trailing whitespace
    key=$(echo $key | xargs)
    value=$(echo $value | xargs)
    
    # Check if the key is valid (no spaces or invalid chars)
    if [[ ! "$key" =~ [^A-Za-z0-9_] ]]; then
      export "$key=$value"
    else
      echo "Skipping invalid key: $key"
    fi
  done < .env
else
  echo ".env file not found"
  exit 1
fi

# Start MySQL service
service mysql start

# Wait for MySQL to be ready
until mysqladmin ping >/dev/null 2>&1; do
  echo "⏳ Waiting for MySQL..."
  sleep 1
done

# Initialize DB if not exists
echo "🔧 Setting up MySQL database..."
mysql -u root -e "CREATE DATABASE IF NOT EXISTS \`${DATABASE_NAME}\`;" 

# Start bot
echo "🐛 Initializing Database"
python main.py

echo "🚀 Running Bot"
python bot.py
