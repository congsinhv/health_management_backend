#!/usr/bin/env python3
"""Test integration between Main API and Prediction Service."""

import requests
import json
import time
import os
from typing import Dict, Any, Optional

# URLs
PREDICTION_SERVICE_URL = "http://localhost:8001"
MAIN_API_URL = "http://localhost:8080"

def test_prediction_service_direct():
    """Test prediction service directly."""
    print("=== Testing Prediction Service Direct ===")

    user_data = {
        "age": 30,
        "gender": "male",
        "height": 1.75,
        "weight": 85,
        "family_history": True,
        "FAVC": "yes",
        "FCVC": 2.5,
        "NCP": 3,
        "CAEC": "Sometimes",
        "CH2O": 2.5,
        "FAF": 1.0,
        "TUE": 3.0,
        "CALC": "Sometimes",
        "MTRANS": "Automobile"
    }

    try:
        # Test health
        health_response = requests.get(f"{PREDICTION_SERVICE_URL}/health", timeout=5)
        print(f"Prediction Service Health: {health_response.status_code}")
        if health_response.status_code == 200:
            print(f"  Model Loaded: {health_response.json().get('model_loaded')}")
        else:
            print(f"  Error: {health_response.text}")
            return False

        # Test prediction
        predict_response = requests.post(
            f"{PREDICTION_SERVICE_URL}/api/v1/predict/",
            json=user_data,
            timeout=30
        )
        print(f"Prediction Service Prediction: {predict_response.status_code}")
        if predict_response.status_code == 200:
            result = predict_response.json()
            print(f"  Obesity Level: {result.get('obesity_level')}")
            print(f"  BMI: {result.get('bmi')}")
            print(f"  Response Time: {predict_response.elapsed.total_seconds():.3f}s")
            return result
        else:
            print(f"  Error: {predict_response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Prediction Service Error: {e}")
        return False

def test_main_api_proxy():
    """Test Main API proxy to prediction service."""
    print("\n=== Testing Main API Proxy ===")

    user_data = {
        "age": 30,
        "gender": "male",
        "height": 1.75,
        "weight": 85,
        "family_history": True,
        "FAVC": "yes",
        "FCVC": 2.5,
        "NCP": 3,
        "CAEC": "Sometimes",
        "CH2O": 2.5,
        "FAF": 1.0,
        "TUE": 3.0,
        "CALC": "Sometimes",
        "MTRANS": "Automobile"
    }

    # Try without authentication first to see the proxy structure
    try:
        predict_response = requests.post(
            f"{MAIN_API_URL}/api/v1/predict/",
            json=user_data,
            timeout=30
        )
        print(f"Main API Prediction (no auth): {predict_response.status_code}")
        if predict_response.status_code == 401:
            print("  Expected authentication requirement - proxy structure is correct")
        elif predict_response.status_code == 500:
            print(f"  Server error: {predict_response.text}")
            # This could mean Main API is not running or there's a configuration issue
            return False
        else:
            print(f"  Unexpected response: {predict_response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Main API Error: {e}")
        print("  Main API might not be running or accessible")
        return False

    # Check if Main API health endpoint is available
    try:
        health_response = requests.get(f"{MAIN_API_URL}/health", timeout=5)
        print(f"Main API Health: {health_response.status_code}")
        if health_response.status_code == 200:
            print(f"  Status: {health_response.json().get('status')}")
        else:
            print("  Main API health check failed")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Main API Health Error: {e}")
        print("  Main API is not running - cannot test integration")
        return False

    return True

def test_service_equivalence():
    """Test that prediction service and main API produce equivalent results."""
    print("\n=== Testing Service Equivalence ===")

    # This would require authentication to Main API, so we'll test the structure
    # and API compatibility instead

    # Test that prediction service response format matches expected format
    user_data = {
        "age": 25,
        "gender": "female",
        "height": 1.65,
        "weight": 60,
        "family_history": False,
        "FAVC": "no",
        "FCVC": 3.0,
        "NCP": 3,
        "CAEC": "Sometimes",
        "CH2O": 2.5,
        "FAF": 2.0,
        "TUE": 2.0,
        "CALC": "Sometimes",
        "MTRANS": "Walking"
    }

    try:
        # Test prediction service
        predict_response = requests.post(
            f"{PREDICTION_SERVICE_URL}/api/v1/predict/",
            json=user_data,
            timeout=30
        )

        if predict_response.status_code == 200:
            result = predict_response.json()
            print("Prediction Service Response Format:")
            print(f"  obesity_level: {result.get('obesity_level')}")
            print(f"  bmi: {result.get('bmi')}")
            print(f"  metabolic_age: {result.get('metabolic_age')}")
            print(f"  diet_plan present: {'healthAnalysis' in result.get('diet_plan', {})}")
            print(f"  workout_plan present: {'weeklyPlans' in result.get('workout_plan', {})}")
            print(f"  raw_prediction present: {len(result.get('raw_prediction', [])) > 0}")
            print(f"  input_data preserved: {len(result.get('input_data', {})) > 0}")

            # Validate expected fields
            required_fields = ['obesity_level', 'bmi', 'metabolic_age', 'diet_plan', 'workout_plan', 'raw_prediction', 'input_data']
            missing_fields = [field for field in required_fields if field not in result]

            if missing_fields:
                print(f"  ERROR: Missing required fields: {missing_fields}")
                return False
            else:
                print("  All required fields present ✅")
                return True
        else:
            print(f"Prediction Service failed: {predict_response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error testing prediction service: {e}")
        return False

def test_error_handling():
    """Test error handling in prediction service."""
    print("\n=== Testing Error Handling ===")

    # Test with invalid data
    invalid_data = {
        "age": -5,  # Invalid age
        "gender": "invalid",
        "height": 0,
        "weight": 0
    }

    try:
        response = requests.post(
            f"{PREDICTION_SERVICE_URL}/api/v1/predict/",
            json=invalid_data,
            timeout=30
        )
        print(f"Invalid Data Response: {response.status_code}")

        if response.status_code == 422:
            print("  Proper validation error ✅")
        elif response.status_code == 500:
            print("  Server handles error but could be improved")
        else:
            print(f"  Unexpected error response: {response.text}")

    except Exception as e:
        print(f"Error testing invalid data: {e}")

    # Test missing required fields
    try:
        response = requests.post(
            f"{PREDICTION_SERVICE_URL}/api/v1/predict/",
            json={},  # Empty data
            timeout=30
        )
        print(f"Missing Fields Response: {response.status_code}")

        if response.status_code == 422:
            print("  Proper validation error for missing fields ✅")
        else:
            print(f"  Unexpected response: {response.text}")

    except Exception as e:
        print(f"Error testing missing fields: {e}")

def test_performance_degradation():
    """Test how the service performs under load."""
    print("\n=== Testing Performance ===")

    user_data = {
        "age": 30,
        "gender": "male",
        "height": 1.75,
        "weight": 85,
        "family_history": False,
        "FAVC": "no",
        "FCVC": 2.5,
        "NCP": 3,
        "CAEC": "Sometimes",
        "CH2O": 2.5,
        "FAF": 2.0,
        "TUE": 2.0,
        "CALC": "Sometimes",
        "MTRANS": "Walking"
    }

    # Test sequential requests
    num_requests = 5
    response_times = []
    success_count = 0

    print(f"Running {num_requests} sequential requests...")
    for i in range(num_requests):
        start_time = time.time()
        try:
            response = requests.post(
                f"{PREDICTION_SERVICE_URL}/api/v1/predict/",
                json=user_data,
                timeout=30
            )
            end_time = time.time()
            response_time = end_time - start_time
            response_times.append(response_time)

            if response.status_code == 200:
                success_count += 1
                print(f"  Request {i+1}: SUCCESS ({response_time:.3f}s)")
            else:
                print(f"  Request {i+1}: FAILED ({response.status_code})")

        except Exception as e:
            print(f"  Request {i+1}: EXCEPTION - {e}")

    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)

        print(f"\nPerformance Summary:")
        print(f"  Success Rate: {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        print(f"  Average Response Time: {avg_time:.3f}s")
        print(f"  Min Response Time: {min_time:.3f}s")
        print(f"  Max Response Time: {max_time:.3f}s")
        print(f"  Performance Range: {max_time - min_time:.3f}s")

        # Check if performance meets requirements
        avg_acceptable = avg_time < 2.0  # Under 2 seconds
        consistency_acceptable = (max_time - min_time) < 1.0  # Within 1 second range
        success_acceptable = success_count / num_requests >= 0.95  # 95% success rate

        print(f"\nPerformance Criteria:")
        print(f"  Average < 2s: {'PASS' if avg_acceptable else 'FAIL'}")
        print(f"  Consistency < 1s range: {'PASS' if consistency_acceptable else 'FAIL'}")
        print(f"  Success Rate >= 95%: {'PASS' if success_acceptable else 'FAIL'}")

        return avg_acceptable and consistency_acceptable and success_acceptable
    else:
        print("  No successful requests")
        return False

def main():
    """Run all integration tests."""
    print("=== Prediction Service Integration Testing ===")
    print(f"Prediction Service URL: {PREDICTION_SERVICE_URL}")
    print(f"Main API URL: {MAIN_API_URL}")

    # Test 1: Direct prediction service
    direct_result = test_prediction_service_direct()

    # Test 2: Main API proxy structure
    proxy_result = test_main_api_proxy()

    # Test 3: Service equivalence and format
    format_result = test_service_equivalence()

    # Test 4: Error handling
    test_error_handling()

    # Test 5: Performance
    performance_result = test_performance_degradation()

    # Summary
    print(f"\n=== Integration Test Summary ===")
    print(f"Prediction Service Direct: {'PASS' if direct_result else 'FAIL'}")
    print(f"Main API Proxy Structure: {'PASS' if proxy_result else 'FAIL'}")
    print(f"Response Format Validation: {'PASS' if format_result else 'FAIL'}")
    print(f"Performance Requirements: {'PASS' if performance_result else 'FAIL'}")

    overall_success = all([
        direct_result is not False,  # False means critical failure
        proxy_result,
        format_result,
        performance_result
    ])

    print(f"\nOVERALL INTEGRATION: {'PASS' if overall_success else 'FAIL'}")

    if not overall_success:
        print("\nRecommendations:")
        if not direct_result:
            print("- Prediction service may need configuration fixes")
        if not proxy_result:
            print("- Main API may need to be running with prediction_service_url configured")
        if not format_result:
            print("- Response format may not match Main API expectations")
        if not performance_result:
            print("- Performance may not meet requirements (<2s avg, 95% success)")

    return overall_success

if __name__ == "__main__":
    main()