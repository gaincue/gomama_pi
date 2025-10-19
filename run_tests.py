#!/usr/bin/env python3
"""
Test runner for GoMama Pi MQTT migration
Runs all unit tests and generates coverage reports
"""

import sys
import subprocess
import os
from pathlib import Path

def run_python_tests():
    """Run Python unit tests"""
    print("🐍 Running Python unit tests...")

    # Install test dependencies if needed
    print("Installing test dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "coverage", "pytest-cov"], check=True)

    # Run tests with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0

def run_typescript_tests():
    """Run TypeScript unit tests"""
    print("🟦 Running TypeScript unit tests...")
    
    # Change to gomama_realtime directory
    os.chdir("gomama_realtime")
    
    try:
        # Install dependencies if needed
        if not os.path.exists("node_modules"):
            print("Installing Node.js dependencies...")
            subprocess.run(["npm", "install"], check=True)
        
        # Install test dependencies
        subprocess.run(["npm", "install", "--save-dev", "vitest", "@vitest/coverage-v8"], check=True)
        
        # Run tests
        result = subprocess.run(["npm", "test"], capture_output=True, text=True)
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    finally:
        # Change back to root directory
        os.chdir("..")

def main():
    """Main test runner"""
    print("🧪 GoMama Pi MQTT Migration - Test Suite")
    print("=" * 50)
    
    # Track test results
    python_success = False
    typescript_success = False
    
    # Run Python tests
    try:
        python_success = run_python_tests()
        if python_success:
            print("✅ Python tests passed!")
        else:
            print("❌ Python tests failed!")
    except Exception as e:
        print(f"❌ Error running Python tests: {e}")
    
    print("\n" + "=" * 50 + "\n")
    
    # Run TypeScript tests
    try:
        typescript_success = run_typescript_tests()
        if typescript_success:
            print("✅ TypeScript tests passed!")
        else:
            print("❌ TypeScript tests failed!")
    except Exception as e:
        print(f"❌ Error running TypeScript tests: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"Python Tests: {'✅ PASS' if python_success else '❌ FAIL'}")
    print(f"TypeScript Tests: {'✅ PASS' if typescript_success else '❌ FAIL'}")
    
    if python_success and typescript_success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
