import unittest
from unittest.mock import MagicMock
import os
import sys

# Add the project root to the Python path to allow imports from other modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the necessary components from FastAPI and your application
from fastapi.testclient import TestClient
from main import app, get_db_manager # Import the app and the dependency provider

# --- THE MOCK DATABASE MANAGER ---
# We create a single mock instance that we will use for all tests.
mock_db_manager = MagicMock()

# --- THE DEFINITIVE FIX: Dependency Overriding ---
# This is the correct, industry-standard way to test FastAPI applications.
# We tell the app: "For this test session, whenever any code asks for the
# `get_db_manager` dependency, give them our `mock_db_manager` instead."
def override_get_db_manager():
    return mock_db_manager

app.dependency_overrides[get_db_manager] = override_get_db_manager


# --- The Test Suite for the AGI's Public API ---

class TestMainAPI(unittest.TestCase):

    def setUp(self):
        """This function runs before each test."""
        # The TestClient will now automatically use our overridden dependency.
        self.client = TestClient(app)
        # Reset the mock before each test to ensure a clean state from previous tests.
        mock_db_manager.reset_mock()

    def test_01_learn_word_endpoint(self):
        """Test 1: Verifies the /learn endpoint for WORDs."""
        print("\nRunning Test 1: /learn WORD endpoint...")
        word_payload = {"learning_type": "WORD", "payload": {"word": "TestWord"}}
        
        response = self.client.post("/learn", json=word_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.learn_word.assert_called_once_with("TestWord")
        print(" -> Test 1 Passed.")

    def test_02_learn_concept_endpoint(self):
        """Test 2: Verifies the /learn endpoint for CONCEPT_LABELING."""
        print("\nRunning Test 2: /learn CONCEPT_LABELING endpoint...")
        concept_payload = {
            "learning_type": "CONCEPT_LABELING",
            "payload": {"word": "Socrates", "concept_name": "Socrates_Concept"}
        }
        
        response = self.client.post("/learn", json=concept_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.label_concept.assert_called_once_with("Socrates", "Socrates_Concept")
        print(" -> Test 2 Passed.")

    def test_03_learn_fact_endpoint(self):
        """Test 3: Verifies the /learn endpoint for FACTs."""
        print("\nRunning Test 3: /learn FACT endpoint...")
        fact_payload = {
            "learning_type": "FACT",
            "payload": {"subject": "Socrates", "relationship": "IS_A", "object": "Man"}
        }
        
        response = self.client.post("/learn", json=fact_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.learn_fact.assert_called_once()
        print(" -> Test 3 Passed.")

    def test_04_query_endpoint(self):
        """Test 4: Verifies the /query endpoint."""
        print("\nRunning Test 4: /query endpoint...")
        # Configure our mock to return a specific value when `query_fact` is called
        mock_db_manager.query_fact.return_value = ["Man"]

        response = self.client.get("/query?subject=Socrates&relationship=IS_A")

        self.assertEqual(response.status_code, 200)
        mock_db_manager.query_fact.assert_called_once_with(subject="Socrates", relationship="IS_A")
        self.assertEqual(response.json(), {"results": ["Man"]})
        print(" -> Test 4 Passed.")

# This allows the test to be run from the command line
if __name__ == '__main__':
    # This setup ensures we don't start the real Soul's life cycle during tests
    app.dependency_overrides.clear() # Clear overrides if run as main script
    unittest.main()