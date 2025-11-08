#!/bin/bash

# Test script for the AI Code Reviewer API

set -e

BASE_URL="http://localhost:8000"

echo "🧪 Testing AI Code Reviewer API"
echo "================================"
echo ""

# Test 1: Health check
echo "1️⃣  Testing health endpoint..."
HEALTH=$(curl -s $BASE_URL/health)
echo "   Response: $HEALTH"

if echo "$HEALTH" | grep -q '"api":"healthy"'; then
    echo "   ✅ Health check passed"
else
    echo "   ❌ Health check failed"
    exit 1
fi
echo ""

# Test 2: Root endpoint
echo "2️⃣  Testing root endpoint..."
ROOT=$(curl -s $BASE_URL/)
echo "   Response: $ROOT"

if echo "$ROOT" | grep -q '"status":"healthy"'; then
    echo "   ✅ Root endpoint passed"
else
    echo "   ❌ Root endpoint failed"
    exit 1
fi
echo ""

# Test 3: Create review job
echo "3️⃣  Testing review job creation..."
REVIEW_RESPONSE=$(curl -s -X POST $BASE_URL/review \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "octocat/hello-world",
    "base": "abc123def456",
    "head": "def456abc123",
    "pr": 42
  }')

echo "   Response: $REVIEW_RESPONSE"

JOB_ID=$(echo "$REVIEW_RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

if [ -n "$JOB_ID" ]; then
    echo "   ✅ Review job created with ID: $JOB_ID"
else
    echo "   ❌ Failed to create review job"
    exit 1
fi
echo ""

# Test 4: Check job status
echo "4️⃣  Testing job status endpoint..."
sleep 2  # Give it a moment to process

JOB_STATUS=$(curl -s $BASE_URL/jobs/$JOB_ID)
echo "   Response: $JOB_STATUS"

if echo "$JOB_STATUS" | grep -q '"job_id"'; then
    echo "   ✅ Job status retrieved successfully"
else
    echo "   ❌ Failed to get job status"
    exit 1
fi
echo ""

# Test 5: Get policy
echo "5️⃣  Testing policy endpoint..."
POLICY=$(curl -s $BASE_URL/config/policy)
echo "   Response: $POLICY"

if echo "$POLICY" | grep -q '"max_loc"'; then
    echo "   ✅ Policy retrieved successfully"
else
    echo "   ❌ Failed to get policy"
    exit 1
fi
echo ""

# Test 6: Update policy
echo "6️⃣  Testing policy update..."
POLICY_UPDATE=$(curl -s -X POST $BASE_URL/config/policy \
  -H "Content-Type: application/json" \
  -d '{
    "denylist": ["auth/**", "secrets/**"],
    "max_loc": 40,
    "auto_commit_threshold": 0.3,
    "max_files_per_patch": 5
  }')

echo "   Response: $POLICY_UPDATE"

if echo "$POLICY_UPDATE" | grep -q '"success":true'; then
    echo "   ✅ Policy updated successfully"
else
    echo "   ❌ Failed to update policy"
    exit 1
fi
echo ""

echo "================================"
echo "✅ All tests passed!"
echo "================================"
echo ""
echo "📊 Summary:"
echo "   • Health check: ✓"
echo "   • Root endpoint: ✓"
echo "   • Review creation: ✓"
echo "   • Job status: ✓"
echo "   • Policy get/update: ✓"
echo ""
echo "🎉 Your AI Code Reviewer API is working correctly!"
echo ""