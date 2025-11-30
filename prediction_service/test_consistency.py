#!/usr/bin/env python3
"""Test prediction consistency and performance."""

import requests
import json
import time
import statistics
from typing import List, Dict, Any

# Base URL for prediction service
BASE_URL = "http://localhost:8001"

def test_prediction_consistency():
    """Test prediction consistency with same input multiple times."""

    # Test user data
    user_data = {
        "age": 28,
        "gender": "female",
        "height": 1.68,
        "weight": 72,
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

    num_tests = 10
    results = []
    response_times = []

    print(f"Testing prediction consistency with {num_tests} identical requests...")
    print(f"Input data: {json.dumps(user_data, indent=2)}")

    for i in range(num_tests):
        start_time = time.time()

        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/predict/",
                json=user_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            end_time = time.time()
            response_time = end_time - start_time
            response_times.append(response_time)

            if response.status_code == 200:
                result = response.json()
                results.append(result)
                print(f"Test {i+1}: {result['obesity_level']} (BMI: {result['bmi']}, Response: {response_time:.3f}s)")
            else:
                print(f"Test {i+1}: FAILED with status {response.status_code}")
                print(f"Error: {response.text}")

        except Exception as e:
            print(f"Test {i+1}: EXCEPTION - {e}")

    # Analyze consistency
    if results:
        obesity_levels = [r['obesity_level'] for r in results]
        bmi_values = [r['bmi'] for r in results]
        metabolic_ages = [r['metabolic_age'] for r in results]

        # Check consistency
        unique_obesity_levels = set(obesity_levels)
        bmi_variance = statistics.variance(bmi_values) if len(bmi_values) > 1 else 0

        print(f"\n=== Consistency Analysis ===")
        print(f"Total successful predictions: {len(results)}/{num_tests}")
        print(f"Unique obesity levels: {unique_obesity_levels}")
        print(f"Obesity level consistency: {len(unique_obesity_levels) == 1}")
        print(f"BMI values: {bmi_values}")
        print(f"BMI variance: {bmi_variance:.6f}")
        print(f"BMI range: {min(bmi_values):.2f} - {max(bmi_values):.2f}")
        print(f"Metabolic ages: {metabolic_ages}")

        # Performance analysis
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)

        print(f"\n=== Performance Analysis ===")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Min response time: {min_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Response time range: {max_response_time - min_response_time:.3f}s")

        # Consistency criteria
        is_consistent = (
            len(unique_obesity_levels) == 1 and
            bmi_variance < 0.001 and  # BMI should be exactly the same
            max_response_time - min_response_time < 2.0  # Response times reasonably consistent
        )

        print(f"\n=== Consistency Result ===")
        print(f"Overall consistency: {'PASS' if is_consistent else 'FAIL'}")

        return {
            'success_rate': len(results) / num_tests,
            'obesity_consistency': len(unique_obesity_levels) == 1,
            'bmi_variance': bmi_variance,
            'avg_response_time': avg_response_time,
            'overall_consistent': is_consistent
        }
    else:
        print("ERROR: No successful predictions!")
        return {'success_rate': 0, 'overall_consistent': False}

def test_onnx_performance():
    """Test ONNX model performance specifically."""

    # Test with varied inputs to see model performance
    test_cases = [
        {"name": "Underweight", "age": 22, "gender": "female", "height": 1.65, "weight": 45},
        {"name": "Normal", "age": 30, "gender": "male", "height": 1.75, "weight": 70},
        {"name": "Overweight", "age": 35, "gender": "female", "height": 1.60, "weight": 75},
        {"name": "Obese", "age": 45, "gender": "male", "height": 1.70, "weight": 95}
    ]

    # Base template
    base_data = {
        "family_history": False,
        "FAVC": "no",
        "FCVC": 2.5,
        "NCP": 3,
        "CAEC": "Sometimes",
        "CH2O": 2.0,
        "FAF": 1.5,
        "TUE": 2.5,
        "CALC": "Sometimes",
        "MTRANS": "Walking"
    }

    print(f"\n=== ONNX Model Performance Test ===")

    for test_case in test_cases:
        # Merge test case with base data
        user_data = {**base_data, **test_case}
        test_name = user_data.pop("name")

        # Multiple runs for performance measurement
        times = []
        for i in range(5):
            start_time = time.time()

            try:
                response = requests.post(
                    f"{BASE_URL}/api/v1/predict/",
                    json=user_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                end_time = time.time()
                response_time = end_time - start_time

                if response.status_code == 200:
                    times.append(response_time)

            except Exception as e:
                print(f"  {test_name} run {i+1}: FAILED - {e}")

        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)

            print(f"  {test_name}:")
            print(f"    Avg: {avg_time:.3f}s")
            print(f"    Range: {min_time:.3f}s - {max_time:.3f}s")
        else:
            print(f"  {test_name}: FAILED (no successful predictions)")

if __name__ == "__main__":
    print("=== Prediction Service Consistency & Performance Testing ===")

    # Test consistency
    consistency_results = test_prediction_consistency()

    # Test ONNX performance
    test_onnx_performance()

    # Summary
    print(f"\n=== Final Summary ===")
    print(f"Success Rate: {consistency_results['success_rate']*100:.1f}%")
    print(f"Obesity Level Consistency: {consistency_results['obesity_consistency']}")
    print(f"BMI Variance: {consistency_results['bmi_variance']:.6f}")
    print(f"Average Response Time: {consistency_results['avg_response_time']:.3f}s")
    print(f"Overall Consistency: {consistency_results['overall_consistent']}")

    # Success criteria based on requirements
    success_criteria = {
        'success_rate': consistency_results['success_rate'] >= 0.95,
        'obesity_consistency': consistency_results['obesity_consistency'],
        'bmi_variance_acceptable': consistency_results['bmi_variance'] < 0.001,
        'response_time_acceptable': consistency_results['avg_response_time'] < 2.0,
        'overall_pass': consistency_results['overall_consistent']
    }

    print(f"\n=== Success Criteria ===")
    for criteria, passed in success_criteria.items():
        print(f"{criteria}: {'PASS' if passed else 'FAIL'}")

    overall_pass = all(success_criteria.values())
    print(f"\nOVERALL: {'PASS' if overall_pass else 'FAIL'}")