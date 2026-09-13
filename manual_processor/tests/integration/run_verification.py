"""
Run all three test sets to verify infrastructure is working
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "manual_processor"))

# Setup test environment
from tests.integration.test_config import setup_test_environment
setup_test_environment

def run_test_module(module_name):
    """Run a test module and return success status"""
    try:
        # Import and run the test module's main function if it exists
        module = __import__(f"tests.integration.{module_name}", fromlist=[""])
        if hasattr(module, "main"):
            module.main()
        else:
            # For test classes, we'll run them manually
            print(f"Running {module_name}... (manual verification)")
        return True
    except Exception as e:
        print(f"❌ {module_name} failed: {e}")
        return False

def main():
    print("Running infrastructure verification tests (steps 4-6)...")
    print("=" * 60)
    
    tests = [
        ("test_health_config", "Health & Configuration Endpoints"),
        ("test_file_upload_download", "File Upload/Download Endpoints"), 
        ("test_processing_flow", "Processing Flow Endpoints")
    ]
    
    passed = 0
    total = len(tests)
    
    for test_module, test_name in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        try:
            # Run the test module
            if test_module == "test_health_config":
                from tests.integration import test_health_config
                test_health_config.TestHealthConfig().setup_method()
                test_health_config.TestHealthConfig().test_health_endpoint_returns_200()
                test_health_config.TestHealthConfig().test_health_endpoint_structure()
                test_health_config.TestHealthConfig().test_config_endpoint_exists()
                test_health_config.TestHealthConfig().test_i18n_languages_endpoint_exists()
                test_health_config.TestHealthConfig().test_i18n_translations_endpoint_exists()
                test_health_config.TestHealthConfig().test_set_language_endpoint_exists()
                test_health_config.TestHealthConfig().test_detect_language_endpoint_exists()
                print("  ✓ All health/config tests passed")
                
            elif test_module == "test_file_upload_download":
                from tests.integration import test_file_upload_download
                test_instance = test_file_upload_download.TestFileUploadDownload()
                test_instance.setup_method()
                test_instance.test_upload_endpoint_exists()
                test_instance.test_list_uploads_endpoint_exists()
                test_instance.test_delete_upload_endpoint_exists()
                test_instance.test_download_endpoint_exists()
                test_instance.test_create_valid_pdf()
                test_instance.test_pdf_structure()
                print("  ✓ All file upload/download tests passed")
                
            elif test_module == "test_processing_flow":
                from tests.integration import test_processing_flow
                test_instance = test_processing_flow.TestProcessingFlow()
                test_instance.setup_method()
                test_instance.test_process_endpoint_exists()
                test_instance.test_get_result_endpoint_exists()
                test_instance.test_create_test_file_id()
                test_instance.test_processing_options_structure()
                test_instance.test_mermaid_endpoints_exist()
                test_instance.test_security_endpoints_exist()
                test_instance.test_drive_endpoints_exist()
                test_instance.test_observability_endpoints_exist()
                print("  ✓ All processing flow tests passed")
            
            passed += 1
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} test sets passed")
    
    if passed == total:
        print("🎉 All infrastructure verification tests passed!")
        print("✅ Steps 4, 5, and 6 are working correctly!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)