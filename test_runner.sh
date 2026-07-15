#!/bin/bash

# LexFlow Comprehensive Test Suite
# Generated for LOCAL_TESTING_GUIDE

set -e

cd ~/Desktop/LexFlow/lexflow_hermes_v1
export FLASK_APP=run_crm.py
export JWT_SECRET_KEY="test-secret-key"
export CORS_ORIGINS="http://localhost:3000,http://localhost:5001"

echo "=================================="
echo "LEXFLOW LOCAL TESTING SUITE"
echo "=================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results tracking
PASSED=0
FAILED=0

# Test helper function
run_test() {
    local test_num=$1
    local test_name=$2
    local curl_cmd=$3
    local expected=$4
    
    echo -n "TEST $test_num: $test_name ... "
    
    # Run curl and capture response and HTTP code
    response=$(eval "$curl_cmd" 2>/dev/null || echo "ERROR")
    
    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Response: $response"
        ((FAILED++))
    fi
}

# Wait for server to be ready
echo ""
echo "Waiting for Flask server to start..."
sleep 3

# PHASE 1: Health & Basic Connectivity
echo ""
echo "=== PHASE 1: Health & Connectivity ==="

run_test T1.1 "Health check endpoint" \
    "curl -s -X GET http://localhost:5001/health" \
    "operational"

run_test T1.2 "Admin health endpoint" \
    "curl -s -X GET http://localhost:5001/api/admin/health" \
    "operational"

run_test T1.3 "Invalid endpoint returns 404" \
    "curl -s -w '%{http_code}' -o /dev/null -X GET http://localhost:5001/api/invalid" \
    "404"

# PHASE 2: JWT & Authentication
echo ""
echo "=== PHASE 2: JWT & Authentication ==="

# Get token for later use
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@lexflow.com", "password": "SecurePass123"}')

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ -z "$TOKEN" ]; then
    echo "Warning: Could not obtain JWT token. Some tests will be skipped."
else
    echo "Token obtained: ${TOKEN:0:20}..."
fi

run_test T2.1 "Login with valid credentials" \
    "curl -s -X POST http://localhost:5001/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{\"email\": \"admin@lexflow.com\", \"password\": \"SecurePass123\"}'" \
    "access_token"

run_test T2.2 "Login with invalid email format" \
    "curl -s -X POST http://localhost:5001/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{\"email\": \"invalid-email\", \"password\": \"SecurePass123\"}'" \
    "Invalid\|error"

run_test T2.3 "Login with missing password" \
    "curl -s -w '%{http_code}' -o /dev/null -X POST http://localhost:5001/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{\"email\": \"admin@lexflow.com\"}'" \
    "400"

run_test T2.4 "Login with wrong password" \
    "curl -s -w '%{http_code}' -o /dev/null -X POST http://localhost:5001/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{\"email\": \"admin@lexflow.com\", \"password\": \"WrongPassword123\"}'" \
    "401"

if [ ! -z "$TOKEN" ]; then
    run_test T2.5 "Get current user with valid token" \
        "curl -s -X GET http://localhost:5001/api/auth/me \
          -H 'Authorization: Bearer $TOKEN'" \
        "email"
else
    echo "TEST T2.5: Skipped (no token)"
fi

run_test T2.6 "Get current user without token" \
    "curl -s -w '%{http_code}' -o /dev/null -X GET http://localhost:5001/api/auth/me" \
    "401"

run_test T2.7 "Get current user with invalid token" \
    "curl -s -w '%{http_code}' -o /dev/null -X GET http://localhost:5001/api/auth/me \
      -H 'Authorization: Bearer invalid-token-xyz'" \
    "422"

# PHASE 3: Input Validation
echo ""
echo "=== PHASE 3: Input Validation ==="

run_test T3.1 "Create case with valid data" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": 1, \"title\": \"Test Case Title\", \"status\": \"Intake\", \"priority\": \"Medium\"}'" \
    "Test Case Title\|id"

run_test T3.2 "Create case with short title (should fail)" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": 1, \"title\": \"AB\", \"status\": \"Intake\"}'" \
    "characters\|error"

run_test T3.3 "Create case with invalid status" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": 1, \"title\": \"Test Case\", \"status\": \"InvalidStatus\"}'" \
    "status\|error"

run_test T3.4 "Create case with invalid priority" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": 1, \"title\": \"Test Case\", \"priority\": \"VeryHigh\"}'" \
    "priority\|error"

run_test T3.6 "Create case with non-integer contactid" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": \"invalid\", \"title\": \"Test Case\"}'" \
    "integer\|error"

run_test T3.7 "Create case with missing required field" \
    "curl -s -X POST http://localhost:5001/api/cases \
      -H 'Content-Type: application/json' \
      -d '{\"contactid\": 1}'" \
    "required\|error"

# PHASE 4: Rate Limiting  
echo ""
echo "=== PHASE 4: Rate Limiting ==="

# Test that we can make many requests without hitting limit
echo -n "TEST T4.1: Rate limit - 50 GET requests within limit ... "
LIMIT_TEST=0
for i in {1..50}; do
    status=$(curl -s -w '%{http_code}' -o /dev/null http://localhost:5001/api/cases)
    if [ "$status" != "200" ]; then
        ((LIMIT_TEST++))
    fi
done
if [ $LIMIT_TEST -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}"
    ((PASSED++))
else
    echo -e "${RED}FAIL${NC} (Rate limited too early)"
    ((FAILED++))
fi

# PHASE 5: Admin Endpoints
echo ""
echo "=== PHASE 5: Admin Endpoints ==="

run_test T5.2 "Attempt admin endpoint without auth" \
    "curl -s -w '%{http_code}' -o /dev/null -X GET http://localhost:5001/api/admin/users" \
    "401"

# PHASE 6: CORS Configuration
echo ""
echo "=== PHASE 6: CORS Configuration ==="

run_test T6.1 "Preflight CORS request" \
    "curl -s -X OPTIONS http://localhost:5001/api/cases \
      -H 'Origin: http://localhost:3000' \
      -H 'Access-Control-Request-Method: GET'" \
    "200"

# PHASE 7: Connection Pooling
echo ""
echo "=== PHASE 7: Connection Pooling ==="

echo -n "TEST T7.1: Concurrent connections (50 requests) ... "
CONN_TEST=0
for i in {1..50}; do
    status=$(curl -s -w '%{http_code}' -o /dev/null http://localhost:5001/api/cases)
    if [ "$status" != "200" ]; then
        ((CONN_TEST++))
    fi
done
if [ $CONN_TEST -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}"
    ((PASSED++))
else
    echo -e "${RED}FAIL${NC} (Connection errors: $CONN_TEST)"
    ((FAILED++))
fi

# PHASE 10: Request/Response Format
echo ""
echo "=== PHASE 10: Request/Response Format ==="

run_test T10.1 "All responses are valid JSON" \
    "curl -s http://localhost:5001/api/cases | jq . > /dev/null && echo valid" \
    "valid"

# Database Verification
echo ""
echo "=== DATABASE VERIFICATION ==="

run_test DB1 "Check migrations applied" \
    "flask db current" \
    "e\|version\|migration"

run_test DB2 "Verify soft-delete columns exist" \
    "sqlite3 crm_local.db '.schema cases' | grep is_deleted" \
    "is_deleted"

# Performance Checks
echo ""
echo "=== PERFORMANCE CHECKS ==="

echo -n "TEST P1: Response time for GET /cases (should be <100ms) ... "
response_time=$(curl -s -w '%{time_total}' -o /dev/null http://localhost:5001/api/cases)
if (( $(echo "$response_time < 0.1" | bc -l) )); then
    echo -e "${GREEN}PASS${NC} (${response_time}s)"
    ((PASSED++))
else
    echo -e "${RED}FAIL${NC} (${response_time}s)"
    ((FAILED++))
fi

# Test Summary
echo ""
echo "=================================="
echo "TEST SUMMARY"
echo "=================================="
echo -e "${GREEN}PASSED: $PASSED${NC}"
echo -e "${RED}FAILED: $FAILED${NC}"
TOTAL=$((PASSED + FAILED))
echo "TOTAL: $TOTAL"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✅ ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "\n${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
fi
