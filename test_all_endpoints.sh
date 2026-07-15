#!/bin/bash
# Comprehensive endpoint testing script for LexFlow CRM

HOST="http://localhost:5001"
PASSED=0
FAILED=0
TESTS=()

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test helper function
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    local expected_status=$5
    local auth_token=$6
    
    echo -n "Testing: $name... "
    
    if [ -z "$data" ]; then
        if [ -z "$auth_token" ]; then
            response=$(curl -s -w "\n%{http_code}" -X "$method" "$HOST$endpoint")
        else
            response=$(curl -s -w "\n%{http_code}" -X "$method" "$HOST$endpoint" -H "Authorization: Bearer $auth_token")
        fi
    else
        if [ -z "$auth_token" ]; then
            response=$(curl -s -w "\n%{http_code}" -X "$method" "$HOST$endpoint" -H "Content-Type: application/json" -d "$data")
        else
            response=$(curl -s -w "\n%{http_code}" -X "$method" "$HOST$endpoint" -H "Content-Type: application/json" -H "Authorization: Bearer $auth_token" -d "$data")
        fi
    fi
    
    status_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} ($status_code)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC} (Expected: $expected_status, Got: $status_code) - Response: $body"
        ((FAILED++))
    fi
}

echo "================================"
echo "LexFlow CRM - Comprehensive Tests"
echo "================================"
echo ""

# Test 1: Health check
echo "=== HEALTH CHECKS ==="
test_endpoint "Health Check" "GET" "/health" "" "200"

# Test 2: Admin health check (no auth)
test_endpoint "Admin Health Check (No Auth)" "GET" "/api/admin/health" "" "200"

# Test 3: Invalid login (missing email)
echo ""
echo "=== INPUT VALIDATION TESTS ==="
test_endpoint "Login - Missing Email" "POST" "/api/auth/login" '{"password":"test"}' "400"

# Test 4: Invalid login (invalid email format)
test_endpoint "Login - Invalid Email Format" "POST" "/api/auth/login" '{"email":"notanemail","password":"test"}' "400"

# Test 5: Invalid login (password too short)
test_endpoint "Login - Invalid Password (too short)" "POST" "/api/auth/login" '{"email":"test@test.com","password":"short"}' "400"

# Test 6: Rate limiting test (login - 10 per minute limit)
echo ""
echo "=== RATE LIMITING TESTS (Sequential Login Attempts) ==="
for i in {1..11}; do
    if [ $i -le 10 ]; then
        test_endpoint "Login Attempt $i (under limit)" "POST" "/api/auth/login" '{"email":"test@test.com","password":"TestPass123"}' "401"
    else
        test_endpoint "Login Attempt $i (exceeds limit)" "POST" "/api/auth/login" '{"email":"test@test.com","password":"TestPass123"}' "429"
    fi
done

# Test 7: Create contact (for foreign key dependency)
echo ""
echo "=== CONTACTS ENDPOINT ==="
test_endpoint "Create Contact" "POST" "/contacts" '{"name":"Test Contact","email":"contact@test.com","phone":"1234567890"}' "201"

# Test 8: Get contacts
test_endpoint "Get Contacts" "GET" "/contacts" "" "200"

# Test 9: Create case with validation
echo ""
echo "=== CASES ENDPOINT WITH VALIDATION ==="
test_endpoint "Create Case - Missing Title" "POST" "/cases" '{"contactid":1}' "400"

# Test 10: Create case - title too short
test_endpoint "Create Case - Title Too Short" "POST" "/cases" '{"contactid":1,"title":"AB"}' "400"

# Test 11: Create case - invalid status
test_endpoint "Create Case - Invalid Status" "POST" "/cases" '{"contactid":1,"title":"Valid Case","status":"InvalidStatus"}' "400"

# Test 12: Get cases
test_endpoint "Get Cases" "GET" "/cases" "" "200"

# Test 13: Admin endpoints (no auth - should fail)
echo ""
echo "=== ADMIN ENDPOINTS (NO AUTH) ==="
test_endpoint "Admin Users List - No Auth" "GET" "/api/admin/users" "" "401"

# Test 14: Admin stats - no auth
test_endpoint "Admin Stats - No Auth" "GET" "/api/admin/stats" "" "401"

# Test 15: CORS check (verify headers)
echo ""
echo "=== CORS CHECKS ==="
cors_response=$(curl -s -i -X OPTIONS "http://localhost:5001/api/admin/health")
if echo "$cors_response" | grep -q "Access-Control-Allow-Origin"; then
    echo -e "CORS Headers Present: ${GREEN}✓ PASS${NC}"
    ((PASSED++))
else
    echo -e "CORS Headers Missing: ${RED}✗ FAIL${NC}"
    ((FAILED++))
fi

# Summary
echo ""
echo "================================"
echo "TEST SUMMARY"
echo "================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total:  $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
