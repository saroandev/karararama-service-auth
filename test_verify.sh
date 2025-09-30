#!/bin/bash

echo "🔐 Testing Token Verification Endpoint"
echo ""

# 1. Login
echo "1️⃣ Login as admin user..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}')

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "✅ Token received: ${TOKEN:0:50}..."
echo ""

# 2. Verify token
echo "2️⃣ Verifying token at /auth/verify endpoint..."
echo ""

curl -s -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo ""
echo "✅ This response should be returned to other services!"
