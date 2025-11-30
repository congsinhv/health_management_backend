#!/usr/bin/env python3
"""Test error handling and graceful degradation in prediction service."""

import requests
import json
import time
from typing import Dict, Any, List

# Base URL for prediction service
BASE_URL = "http://localhost:8001"

def test_invalid_data_scenarios():
    """Test various invalid data scenarios."""
    print("=== Testing Invalid Data Scenarios ===")

    test_cases = [
        {
            "name": "Negative Age",
            "data": {
                "age": -5,
                "gender": "male",
                "height": 1.75,
                "weight": 70,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 2.5,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.0,
                "FAF": 1.0,
                "TUE": 2.0,
                "CALC": "Sometimes",
                "MTRANS": "Walking"
            },
            "expected_status": 422
        },
        {
            "name": "Zero Height",
            "data": {
                "age": 30,
                "gender": "male",
                "height": 0,
                "weight": 70,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 2.5,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.0,
                "FAF": 1.0,
                "TUE": 2.0,
                "CALC": "Sometimes",
                "MTRANS": "Walking"
            },
            "expected_status": 422
        },
        {
            "name": "Invalid Gender",
            "data": {
                "age": 30,
                "gender": "invalid_gender",
                "height": 1.75,
                "weight": 70,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 2.5,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.0,
                "FAF": 1.0,
                "TUE": 2.0,
                "CALC": "Sometimes",
                "MTRANS": "Walking"
            },
            "expected_status": 500  # This might pass validation but fail in processing
        },
        {
            "name": "Missing Required Fields",
            "data": {
                "age": 30,
                "gender": "male"
                # Missing height, weight, etc.
            },
            "expected_status": 422
        },
        {
            "name": "Empty Data",
            "data": {},
            "expected_status": 422
        },
        {
            "name": "Null Values",
            "data": {
                "age": None,
                "gender": None,
                "height": None,
                "weight": None,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 2.5,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.0,
                "FAF": 1.0,
                "TUE": 2.0,
                "CALC": "Sometimes",
                "MTRANS": "Walking"
            },
            "expected_status": 422
        },
        {
            "name": "Extreme Values",
            "data": {
                "age": 150,
                "gender": "male",
                "height": 3.0,
                "weight": 300,
                "family_history": True,
                "FAVC": "yes",
                "FCVC": 5.0,
                "NCP": 10,
                "CAEC": "Always",
                "CH2O": 10.0,
                "FAF": 10.0,
                "TUE": 20.0,
                "CALC": "Always",
                "MTRANS": "Automobile"
            },
            "expected_status": 200  # Should handle extreme values gracefully
        }
    ]

    results = []

    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")

        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/api/v1/predict/",
                json=test_case['data'],
                timeout=30
            )
            end_time = time.time()
            response_time = end_time - start_time

            print(f"Status Code: {response.status_code} (Expected: {test_case['expected_status']})")
            print(f"Response Time: {response_time:.3f}s")

            if response.status_code == test_case['expected_status']:
                print("✅ Status code matches expectation")
                results.append(True)
            else:
                print("❌ Status code doesn't match expectation")
                results.append(False)

            if response.status_code == 422:
                # Validation error - should have proper error message
                error_data = response.json()
                print(f"Validation Error: {error_data.get('detail', 'No error details')}")
                if 'detail' in error_data:
                    print("✅ Proper error response format")
                else:
                    print("❌ Missing error details")

            elif response.status_code == 500:
                # Internal server error - should have error message
                print(f"Server Error: {response.text}")
                if 'detail' in response.text:
                    print("✅ Error response contains details")
                else:
                    print("❌ Error response lacks details")

            elif response.status_code == 200:
                # Success - check if response is reasonable
                result = response.json()
                required_fields = ['obesity_level', 'bmi', 'metabolic_age', 'diet_plan', 'workout_plan']
                missing_fields = [field for field in required_fields if field not in result]

                if missing_fields:
                    print(f"❌ Missing fields: {missing_fields}")
                    results.append(False)
                else:
                    print("✅ Response contains all required fields")

                # Check if values are reasonable
                bmi = result.get('bmi', 0)
                metabolic_age = result.get('metabolic_age', 0)

                if not (10 <= bmi <= 100):
                    print(f"❌ Unreasonable BMI: {bmi}")
                    results.append(False)
                elif not (10 <= metabolic_age <= 100):
                    print(f"❌ Unreasonable metabolic age: {metabolic_age}")
                    results.append(False)
                else:
                    print("✅ Reasonable values returned")

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            results.append(False)

    return results

def test_service_availability():
    """Test service availability and health checks."""
    print("\n=== Testing Service Availability ===")

    endpoints = [
        ("/", "Root"),
        ("/health", "Health Check"),
        ("/api/v1/predict/health", "Prediction Service Health"),
        ("/api/v1/predict/info", "Service Info")
    ]

    availability_results = []

    for endpoint, name in endpoints:
        print(f"\n--- {name} ({endpoint}) ---")

        try:
            start_time = time.time()
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            end_time = time.time()
            response_time = end_time - start_time

            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response_time:.3f}s")

            if response.status_code == 200:
                print("✅ Endpoint is available")

                if endpoint == "/health" or endpoint == "/api/v1/predict/health":
                    health_data = response.json()
                    if 'status' in health_data:
                        print(f"  Status: {health_data['status']}")
                    if 'model_loaded' in health_data:
                        print(f"  Model Loaded: {health_data['model_loaded']}")
                    if health_data.get('model_loaded', False):
                        print("✅ Model is loaded and ready")
                    else:
                        print("❌ Model is not loaded")

                availability_results.append(True)
            else:
                print(f"❌ Endpoint returned {response.status_code}")
                availability_results.append(False)

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            availability_results.append(False)

    return availability_results

def test_concurrent_requests():
    """Test service behavior under concurrent load."""
    print("\n=== Testing Concurrent Requests ===")

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
        "CH2O": 2.0,
        "FAF": 1.0,
        "TUE": 2.0,
        "CALC": "Sometimes",
        "MTRANS": "Walking"
    }

    import threading
    import queue

    results = queue.Queue()
    num_requests = 10

    def make_request(request_id):
        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/api/v1/predict/",
                json=user_data,
                timeout=30
            )
            end_time = time.time()

            results.put({
                'id': request_id,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200
            })
        except Exception as e:
            results.put({
                'id': request_id,
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'error': str(e)
            })

    # Start concurrent requests
    threads = []
    start_time = time.time()

    for i in range(num_requests):
        thread = threading.Thread(target=make_request, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    end_time = time.time()
    total_time = end_time - start_time

    # Collect results
    request_results = []
    while not results.empty():
        request_results.append(results.get())

    # Analyze results
    successful_requests = [r for r in request_results if r['success']]
    failed_requests = [r for r in request_results if not r['success']]

    print(f"Total requests: {num_requests}")
    print(f"Successful requests: {len(successful_requests)}")
    print(f"Failed requests: {len(failed_requests)}")
    print(f"Success rate: {len(successful_requests)/num_requests*100:.1f}%")
    print(f"Total time: {total_time:.3f}s")

    if successful_requests:
        response_times = [r['response_time'] for r in successful_requests]
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)

        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Min response time: {min_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Response time variance: {max_response_time - min_response_time:.3f}s")

    if failed_requests:
        print("\nFailed requests:")
        for failed in failed_requests:
            if 'error' in failed:
                print(f"  Request {failed['id']}: {failed['error']}")
            else:
                print(f"  Request {failed['id']}: Status {failed['status_code']}")

    # Success criteria
    success_rate_acceptable = len(successful_requests) / num_requests >= 0.9  # 90% success rate
    avg_time_acceptable = successful_requests and (sum(r['response_time'] for r in successful_requests) / len(successful_requests)) < 5.0

    print(f"\nConcurrent Load Criteria:")
    print(f"  Success Rate >= 90%: {'PASS' if success_rate_acceptable else 'FAIL'}")
    print(f"  Average Response Time < 5s: {'PASS' if avg_time_acceptable else 'FAIL'}")

    return success_rate_acceptable and avg_time_acceptable

def test_model_edge_cases():
    """Test edge cases that might affect model performance."""
    print("\n=== Testing Model Edge Cases ===")

    edge_cases = [
        {
            "name": "Very Low BMI",
            "data": {
                "age": 20,
                "gender": "female",
                "height": 1.80,
                "weight": 40,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 3.0,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.5,
                "FAF": 5.0,
                "TUE": 1.0,
                "CALC": "no",
                "MTRANS": "Walking"
            }
        },
        {
            "name": "Very High BMI",
            "data": {
                "age": 45,
                "gender": "male",
                "height": 1.65,
                "weight": 120,
                "family_history": True,
                "FAVC": "yes",
                "FCVC": 1.0,
                "NCP": 4,
                "CAEC": "Always",
                "CH2O": 1.0,
                "FAF": 0.0,
                "TUE": 8.0,
                "CALC": "Always",
                "MTRANS": "Automobile"
            }
        },
        {
            "name": "Extreme Age - Young",
            "data": {
                "age": 15,
                "gender": "female",
                "height": 1.60,
                "weight": 50,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 3.0,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.0,
                "FAF": 3.0,
                "TUE": 2.0,
                "CALC": "no",
                "MTRANS": "Bike"
            }
        },
        {
            "name": "Extreme Age - Old",
            "data": {
                "age": 80,
                "gender": "male",
                "height": 1.70,
                "weight": 75,
                "family_history": True,
                "FAVC": "no",
                "FCVC": 2.5,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 2.5,
                "FAF": 1.0,
                "TUE": 3.0,
                "CALC": "Sometimes",
                "MTRANS": "Public_Transportation"
            }
        }
    ]

    edge_case_results = []

    for edge_case in edge_cases:
        print(f"\n--- {edge_case['name']} ---")

        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/predict/",
                json=edge_case['data'],
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                obesity_level = result.get('obesity_level')
                bmi = result.get('bmi')
                metabolic_age = result.get('metabolic_age')

                print(f"Obesity Level: {obesity_level}")
                print(f"BMI: {bmi}")
                print(f"Metabolic Age: {metabolic_age}")
                print("✅ Handled edge case successfully")

                # Check if obesity level makes sense for BMI
                if bmi and obesity_level:
                    if bmi < 18.5 and 'Insufficient' in obesity_level:
                        print("✅ Consistent underweight prediction")
                    elif bmi >= 30 and 'Obesity' in obesity_level:
                        print("✅ Consistent obesity prediction")
                    elif 18.5 <= bmi < 25 and 'Normal' in obesity_level:
                        print("✅ Consistent normal weight prediction")
                    elif 25 <= bmi < 30 and 'Overweight' in obesity_level:
                        print("✅ Consistent overweight prediction")
                    else:
                        print("⚠️  BMI and obesity level may not align")

                edge_case_results.append(True)
            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"Error: {response.text}")
                edge_case_results.append(False)

        except Exception as e:
            print(f"❌ Exception: {e}")
            edge_case_results.append(False)

    return edge_case_results

def main():
    """Run all error handling and degradation tests."""
    print("=== Prediction Service Error Handling & Graceful Degradation Testing ===")

    # Test 1: Invalid data scenarios
    invalid_data_results = test_invalid_data_scenarios()
    invalid_data_pass_rate = sum(invalid_data_results) / len(invalid_data_results) if invalid_data_results else 0

    # Test 2: Service availability
    availability_results = test_service_availability()
    availability_pass_rate = sum(availability_results) / len(availability_results) if availability_results else 0

    # Test 3: Concurrent requests
    concurrent_pass = test_concurrent_requests()

    # Test 4: Model edge cases
    edge_case_results = test_model_edge_cases()
    edge_case_pass_rate = sum(edge_case_results) / len(edge_case_results) if edge_case_results else 0

    # Summary
    print(f"\n=== Error Handling & Degradation Summary ===")
    print(f"Invalid Data Handling: {invalid_data_pass_rate*100:.1f}% pass rate")
    print(f"Service Availability: {availability_pass_rate*100:.1f}% pass rate")
    print(f"Concurrent Load: {'PASS' if concurrent_pass else 'FAIL'}")
    print(f"Edge Case Handling: {edge_case_pass_rate*100:.1f}% pass rate")

    # Overall success criteria
    invalid_data_acceptable = invalid_data_pass_rate >= 0.8  # 80% of invalid cases handled properly
    availability_acceptable = availability_pass_rate >= 0.9  # 90% of endpoints available
    concurrent_acceptable = concurrent_pass  # Concurrent load test passes
    edge_case_acceptable = edge_case_pass_rate >= 0.75  # 75% of edge cases handled

    print(f"\nSuccess Criteria:")
    print(f"  Invalid Data >= 80%: {'PASS' if invalid_data_acceptable else 'FAIL'}")
    print(f"  Service Availability >= 90%: {'PASS' if availability_acceptable else 'FAIL'}")
    print(f"  Concurrent Load: {'PASS' if concurrent_acceptable else 'FAIL'}")
    print(f"  Edge Cases >= 75%: {'PASS' if edge_case_acceptable else 'FAIL'}")

    overall_success = all([invalid_data_acceptable, availability_acceptable, concurrent_acceptable, edge_case_acceptable])
    print(f"\nOVERALL ERROR HANDLING: {'PASS' if overall_success else 'FAIL'}")

    # Recommendations
    if not overall_success:
        print(f"\nRecommendations:")
        if not invalid_data_acceptable:
            print("- Improve validation for invalid data scenarios")
        if not availability_acceptable:
            print("- Check service availability and health endpoints")
        if not concurrent_acceptable:
            print("- Optimize service for concurrent requests")
        if not edge_case_acceptable:
            print("- Test and improve handling of edge cases")

    return overall_success

if __name__ == "__main__":
    main()