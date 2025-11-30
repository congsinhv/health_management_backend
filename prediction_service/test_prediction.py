#!/usr/bin/env python3
"""Test script for prediction service."""

import requests
import json
import time

# Base URL for prediction service
BASE_URL = "http://localhost:8001"


def test_prediction_endpoint():
    """Test the prediction endpoint with sample data."""

    # Test user data
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
        "MTRANS": "Automobile",
    }

    print("Testing prediction endpoint...")
    print(f"Request data: {json.dumps(user_data, indent=2)}")

    try:
        # Make prediction request
        response = requests.post(
            f"{BASE_URL}/api/v1/predict/",
            json=user_data,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"Prediction Result: {json.dumps(result, indent=2, default=str)}")
            return True
        else:
            print(f"Error Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False


def test_multiple_predictions():
    """Test multiple predictions for consistency."""

    test_cases = [
        {
            "name": "Normal BMI male",
            "data": {
                "age": 25,
                "gender": "male",
                "height": 1.80,
                "weight": 75,
                "family_history": False,
                "FAVC": "no",
                "FCVC": 3.0,
                "NCP": 3,
                "CAEC": "Sometimes",
                "CH2O": 3.0,
                "FAF": 3.0,
                "TUE": 2.0,
                "CALC": "Sometimes",
                "MTRANS": "Walking",
            },
        },
        {
            "name": "Overweight female",
            "data": {
                "age": 35,
                "gender": "female",
                "height": 1.65,
                "weight": 80,
                "family_history": True,
                "FAVC": "yes",
                "FCVC": 2.0,
                "NCP": 4,
                "CAEC": "Frequently",
                "CH2O": 1.5,
                "FAF": 0.5,
                "TUE": 4.0,
                "CALC": "Frequently",
                "MTRANS": "Automobile",
            },
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        print(f"\n--- Test Case {i+1}: {test_case['name']} ---")

        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/v1/predict/",
            json=test_case["data"],
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        end_time = time.time()

        response_time = end_time - start_time
        print(f"Response Time: {response_time:.3f}s")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            results.append(
                {
                    "test_name": test_case["name"],
                    "obesity_level": result.get("obesity_level"),
                    "bmi": result.get("bmi"),
                    "response_time": response_time,
                    "success": True,
                }
            )
            print(f"Obesity Level: {result.get('obesity_level')}")
            print(f"BMI: {result.get('bmi')}")
        else:
            print(f"Error: {response.text}")
            results.append(
                {
                    "test_name": test_case["name"],
                    "response_time": response_time,
                    "success": False,
                    "error": response.text,
                }
            )

    return results


if __name__ == "__main__":
    print("=== Prediction Service Testing ===\n")

    # Test basic prediction
    success = test_prediction_endpoint()

    if success:
        print("\n=== Testing Multiple Predictions ===")
        results = test_multiple_predictions()

        print(f"\n=== Summary ===")
        successful_tests = [r for r in results if r["success"]]
        print(f"Successful predictions: {len(successful_tests)}/{len(results)}")

        if successful_tests:
            avg_response_time = sum(r["response_time"] for r in successful_tests) / len(
                successful_tests
            )
            print(f"Average response time: {avg_response_time:.3f}s")

            print("Obesity levels predicted:")
            for result in successful_tests:
                print(
                    f"  {result['test_name']}: {result['obesity_level']} (BMI: {result.get('bmi', 'N/A')})"
                )
    else:
        print("Basic prediction test failed. Skipping consistency tests.")
