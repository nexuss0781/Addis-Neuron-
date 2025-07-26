import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import os
import sys

# Add the project root to the Python path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# --- MOCKING BEFORE IMPORTING ---
# We must mock the DatabaseManager *before* the `main` module is imported,
# because the `main` module creates a global instance of it on load.
mock_db_manager = MagicMock()

# The patch needs to target where the object is *used*, which is in 'main'.
# We replace the global `db_manager` instance in the `main` module with our mock.
@patch('main.db_manager', mock_db_manager)
# We also mock the soul's `live` method so it doesn't run in the background during tests
@patch('main.soul.live')
def import_main_app(mock_soul_live):
    from main import app
    return app

# Perform the import under the patch
app = import_main_app()

# --- The Test Suite for the AGI's Public API ---

class TestMainAPI(unittest.TestCase):

    def setUp(self):
        """This function runs before each test."""
        # Create a test client that can send requests to our app
        self.client = TestClient(app)
        # Reset the mock before each test to ensure a clean state
        mock_db_manager.reset_mock()

    def test_01_learn_word_endpoint(self):
        """
        Test 1: Verifies the /learn endpoint for WORDs.
        """
        print("\nRunning Test 1: /learn WORD endpoint...")
        word_payload = {"learning_type": "WORD", "payload": {"word": "TestWord"}}
        
        response = self.client.post("/learn", json=word_payload)
        
        # Check that the API returned a successful status code
        self.assertEqual(response.status_code, 201)
        # Check that the `learn_word` method on our mock was called with the correct argument
        mock_db_manager.learn_word.assert_called_once_with("TestWord")
        print(" -> Test 1 Passed: /learn WORD correctly calls db_manager.learn_word.")

    def test_02_learn_concept_endpoint(self):
        """
        Test 2: Verifies the /learn endpoint for CONCEPT_LABELING.
        """
        print("\nRunning Test 2: /learn CONCEPT_LABELING endpoint...")
        concept_payload = {
            "learning_type": "CONCEPT_LABELING",
            "payload": {"word": "Socrates", "concept_name": "Socrates_Concept"}
        }
        
        response = self.client.post("/learn", json=concept_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.label_concept.assert_called_once_with("Socrates", "Socrates_Concept")
        print(" -> Test 2 Passed: /learn CONCEPT_LABELING correctly calls db_manager.label_concept.")

    def test_03_learn_fact_endpoint(self):
        """
        Test 3: Verifies the /learn endpoint for FACTs.
        """
        print("\nRunning Test 3: /learn FACT endpoint...")
        fact_payload = {
            "learning_type": "FACT",
            "payload": {"subject": "Socrates", "relationship": "IS_A", "object": "Man"}
        }
        
        response = self.client.post("/learn", json=fact_payload)
        
        self.assertEqual(response.status_code, 201)
        # Check that learn_fact was called, but we don't need to check the arguments
        # as that's a more complex object. Just confirming it was called is enough.
        mock_db_manager.learn_fact.assert_called_once()
        print(" -> Test 3 Passed: /learn FACT correctly calls db_manager.learn_fact.")

    def test_04_query_endpoint(self):
        """
        Test 4: Verifies the /query endpoint.
        """
        print("\nRunning Test 4: /query endpoint...")
        # Configure our mock to return a specific value when `query_fact` is called
        mock_db_manager.query_fact.return_value = ["Man"]

        response = self.client.get("/query?subject=Socrates&relationship=IS_A")

        self.assertEqual(response.status_code, 200)
        # Verify that the query_fact method was called with the correct parameters
        mock_db_manager.query_fact.assert_called_once_with(subject="Socrates", relationship="IS_A")
        # Verify that the API returned the data that our mock provided
        self.assertEqual(response.json(), {"results": ["Man"]})
        print(" -> Test 4 Passed: /query correctly calls db_manager.query_fact and returns data.")

if __name__ == '__main__':
    unittest.main()