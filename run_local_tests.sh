#!/bin/bash

# LexFlow Comprehensive Test Suite
# Automated testing document

cd ~/Desktop/LexFlow/lexflow_hermes_v1

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results
PASSED=0
FAILED=0
SKIPPED=0
TESTS=()

# Log test result
log_test() {
    local test_id=$1
    local test_name=$2
    local result=$3
    local details=$4
    
    if [ "$result" = "PASS" ]; then
        echo -e "✓ ${GREEN}$test_id: $test_name (PASS)${NC}"
        ((PASSED++))
    elif [ "$result" = "FAIL" ]; then
        echo -e "✗ ${RED}$test_id: $test_name (FAIL)${NC}"
        if [ ! -z "$details" ]; then
            echo "  Details: $details"
        fi
        ((FAILED++))
    else
        echo -e "⊘ ${YELLOW}$test_id: $test_name (SKIP)${NC}"
        ((SKIPPED++))
    fi
    
    TESTS+=("$test_id|$result")
}

echo "╔════════════════════════════════════════════════╗"
echo "║   LEXFLOW LOCAL TESTING SUITE - Phase 1 & 2   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# PHASE 1: Health & Connectivity
echo "═══ PHASE 1: Health & Connectivity ═══"

# T1.1 - Health check
response=$(curl -s -w '\n%{http_code}' http://localhost:5001/health)
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)
if [ "$http_code" = "200" ] && echo "$body" | grep -q "ok"; then
    log_test "T1.1" "Health check endpoint" "PASS"
else
    log_test "T1.1" "Health check endpoint" "FAIL" "HTTP $http_code"
fi

# T1.2 - Admin health
response=$(curl -s -w '\n%{http_code}' http://localhost:5001/api/admin/health)
http_code=$(echo "$response" | tail -1)
if [ "$http_code" = "200" ]; then
    log_test "T1.2" "Admin health endpoint" "PASS"
else
    log_test "T1.2" "Admin health endpoint" "FAIL" "HTTP $http_code"
fi

# T1.3 - 404 on invalid endpoint
response=$(curl -s -w '\n%{http_code}' http://localhost:5001/api/invalid)
http_code=$(echo "$response" | tail -1)
if [ "$http_code" = "404" ]; then
    log_test "T1.3" "Invalid endpoint returns 404" "PASS"
else
    log_test "T1.3" "Invalid endpoint returns 404" "FAIL" "HTTP $http_code"
fi

echo ""
echo "═══ PHASE 2: JWT & Authentication ==="

# T2.1 - Valid login
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@lexflow.com", "password": "SecurePass123"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)
TOKEN=$(echo "$body" | grep -o '"access_token":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ "$http_code" = "200" ] && [ ! -z "$TOKEN" ]; then
    log_test "T2.1" "Login with valid credentials" "PASS"
else
    log_test "T2.1" "Login with valid credentials" "FAIL" "HTTP $http_code"
fi

# T2.2 - Invalid email format
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "invalid-email", "password": "SecurePass123"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "invalid\|error"; then
    log_test "T2.2" "Login with invalid email format" "PASS"
else
    log_test "T2.2" "Login with invalid email format" "FAIL" "HTTP $http_code"
fi

# T2.3 - Missing password
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@lexflow.com"}')
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "400" ]; then
    log_test "T2.3" "Login with missing password" "PASS"
else
    log_test "T2.3" "Login with missing password" "FAIL" "HTTP $http_code"
fi

# T2.4 - Wrong password
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@lexflow.com", "password": "WrongPassword123"}')
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "401" ]; then
    log_test "T2.4" "Login with wrong password" "PASS"
else
    log_test "T2.4" "Login with wrong password" "FAIL" "HTTP $http_code"
fi

# T2.5 - Get user with valid token
if [ ! -z "$TOKEN" ]; then
    response=$(curl -s -w '\n%{http_code}' -X GET http://localhost:5001/api/auth/me \
      -H "Authorization: Bearer $TOKEN")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q "email"; then
        log_test "T2.5" "Get current user with valid token" "PASS"
    else
        log_test "T2.5" "Get current user with valid token" "FAIL" "HTTP $http_code"
    fi
else
    log_test "T2.5" "Get current user with valid token" "SKIP"
fi

# T2.6 - Get user without token
response=$(curl -s -w '\n%{http_code}' -X GET http://localhost:5001/api/auth/me)
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "401" ]; then
    log_test "T2.6" "Get current user without token" "PASS"
else
    log_test "T2.6" "Get current user without token" "FAIL" "HTTP $http_code"
fi

# T2.7 - Invalid token
response=$(curl -s -w '\n%{http_code}' -X GET http://localhost:5001/api/auth/me \
  -H "Authorization: Bearer invalidtoken123")
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "422" ] || [ "$http_code" = "401" ]; then
    log_test "T2.7" "Get current user with invalid token" "PASS"
else
    log_test "T2.7" "Get current user with invalid token" "FAIL" "HTTP $http_code"
fi

echo ""
echo "═══ PHASE 3: Input Validation ==="

# T3.1 - Valid case creation
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": 1, "title": "Test Case Title", "status": "Intake", "priority": "Medium"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "201" ] || ([ "$http_code" = "200" ] && echo "$body" | grep -q "Test Case Title"); then
    log_test "T3.1" "Create case with valid data" "PASS"
else
    log_test "T3.1" "Create case with valid data" "FAIL" "HTTP $http_code: $body"
fi

# T3.2 - Short title (min 3 chars)
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": 1, "title": "AB", "status": "Intake"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "characters\|length\|error"; then
    log_test "T3.2" "Short title validation (min 3 chars)" "PASS"
else
    log_test "T3.2" "Short title validation (min 3 chars)" "FAIL" "HTTP $http_code"
fi

# T3.3 - Invalid status
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": 1, "title": "Test Case", "status": "InvalidStatus"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "status\|invalid"; then
    log_test "T3.3" "Invalid status validation" "PASS"
else
    log_test "T3.3" "Invalid status validation" "FAIL" "HTTP $http_code"
fi

# T3.4 - Invalid priority
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": 1, "title": "Test Case", "priority": "VeryHigh"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "priority\|invalid"; then
    log_test "T3.4" "Invalid priority validation" "PASS"
else
    log_test "T3.4" "Invalid priority validation" "FAIL" "HTTP $http_code"
fi

# T3.6 - Non-integer contactid
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": "invalid", "title": "Test Case"}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "integer\|error"; then
    log_test "T3.6" "Non-integer contactid validation" "PASS"
else
    log_test "T3.6" "Non-integer contactid validation" "FAIL" "HTTP $http_code"
fi

# T3.7 - Missing required field
response=$(curl -s -w '\n%{http_code}' -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{"contactid": 1}')
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "400" ] && echo "$body" | grep -qi "required\|error"; then
    log_test "T3.7" "Missing required field validation" "PASS"
else
    log_test "T3.7" "Missing required field validation" "FAIL" "HTTP $http_code"
fi

echo ""
echo "═══ PHASE 4: Rate Limiting ==="

# T4.1 - Within rate limit (50 requests)
echo -n "Testing rate limit (50 requests) ... "
passed_count=0
for i in {1..50}; do
    status=$(curl -s -w '%{http_code}' -o /dev/null http://localhost:5001/api/cases)
    if [ "$status" = "200" ]; then
        ((passed_count++))
    fi
done

if [ $passed_count -ge 48 ]; then  # Allow 2 failures due to timing
    log_test "T4.1" "Rate limit - 50 requests within limit" "PASS"
else
    log_test "T4.1" "Rate limit - 50 requests within limit" "FAIL" "Only $passed_count passed"
fi

echo ""
echo "═══ PHASE 5: Admin Endpoints ==="

# T5.2 - Admin endpoint without auth
response=$(curl -s -w '\n%{http_code}' -X GET http://localhost:5001/api/admin/users)
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "401" ]; then
    log_test "T5.2" "Admin endpoint without auth (401)" "PASS"
else
    log_test "T5.2" "Admin endpoint without auth (401)" "FAIL" "HTTP $http_code"
fi

echo ""
echo "═══ PHASE 6: CORS Configuration ==="

# T6.1 - Preflight CORS
response=$(curl -s -w '\n%{http_code}' -X OPTIONS http://localhost:5001/api/cases \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET")
http_code=$(echo "$response" | tail -1)

if [ "$http_code" = "200" ]; then
    log_test "T6.1" "Preflight CORS request" "PASS"
else
    log_test "T6.1" "Preflight CORS request" "FAIL" "HTTP $http_code"
fi

echo ""
echo "═══ PHASE 10: Request/Response Format ==="

# T10.1 - Valid JSON response
if curl -s http://localhost:5001/api/cases | jq . > /dev/null 2>&1; then
    log_test "T10.1" "All responses are valid JSON" "PASS"
else
    log_test "T10.1" "All responses are valid JSON" "FAIL" "Invalid JSON"
fi

# T10.2 - Error responses have error field
response=$(curl -s -X POST http://localhost:5001/api/cases \
  -H "Content-Type: application/json" \
  -d '{}')

if echo "$response" | grep -q "error"; then
    log_test "T10.2" "Error responses have error field" "PASS"
else
    log_test "T10.2" "Error responses have error field" "FAIL"
fi

echo ""
echo "═══ DATABASE VERIFICATION ==="

# DB1 - Check migrations
if [ -f "crm_local.db" ]; then
    log_test "DB1" "Database file exists" "PASS"
else
    log_test "DB1" "Database file exists" "FAIL"
fi

# DB2 - Check tables
if sqlite3 crm_local.db ".tables" | grep -q "user\|case\|contact"; then
    log_test "DB2" "Database tables exist" "PASS"
else
    log_test "DB2" "Database tables exist" "FAIL"
fi

echo ""
echo "═══ PERFORMANCE CHECKS ==="

# P1 - Response time < 100ms
response_time=$(curl -s -w '%{time_total}' -o /dev/null http://localhost:5001/api/cases)
if (( $(echo "$response_time < 0.1" | bc -l 2>/dev/null) )); then
    log_test "P1" "GET /cases response time < 100ms (${response_time}s)" "PASS"
else
    log_test "P1" "GET /cases response time < 100ms (${response_time}s)" "FAIL"
fi

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║              TEST SUMMARY                      ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${GREEN}✓ PASSED:  $PASSED${NC}"
echo -e "${RED}✗ FAILED:  $FAILED${NC}"
echo -e "${YELLOW}⊘ SKIPPED: $SKIPPED${NC}"
TOTAL=$((PASSED + FAILED))
echo "─────────────────────"
echo "  TOTAL:  $TOTAL"

SUCCESS_RATE=$(( PASSED * 100 / (PASSED + FAILED) ))
echo ""
echo "Success Rate: ${SUCCESS_RATE}%"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✅ ALL CRITICAL TESTS PASSED${NC}"
    exit 0
else
    echo -e "\n${RED}❌ SOME TESTS FAILED - Review above${NC}"
    exit 1
fi
