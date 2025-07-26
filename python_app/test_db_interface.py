import unittest
from unittest.mock import patch, MagicMock
import os
import uuid

# Before we can import the module we're testing, we need to ensure its
# dependencies (like 'models') are in the Python path.
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Now we can import the code we want to test
from db_interface import DatabaseManager
from models import StructuredTriple

# --- The Test Suite for the AGI's Core Cognitive Bridge ---

class TestDatabaseManager(unittest.TestCase):

    @patch('db_interface.redis.StrictRedis')
    @patch('db_interface.requests.post')
    def setUp(self, mock_requests_post, mock_redis):
        """
        This function runs before every single test.
        It creates a fresh, clean instance of the DatabaseManager for each test case.
        """
        # We 'patch' (intercept) the requests.post and redis.StrictRedis calls.
        # This prevents the db_manager from making real network calls.
        
        # Simulate a successful Redis connection
        self.mock_redis_client = MagicMock()
        mock_redis.return_value = self.mock_redis_client

        # We need a fresh instance of the singleton for each test
        if hasattr(DatabaseManager, '_instance'):
            del DatabaseManager._instance
        
        self.db_manager = DatabaseManager()
        # Reset the mock for requests after initialization
        self.db_manager._execute_nlse_plan = MagicMock()

    def test_01_initialization_and_caching(self):
        """
        Test 1: Verifies that the DatabaseManager initializes correctly,
        connects to a mock Redis, and creates its essential caches.
        """
        print("\nRunning Test 1: Initialization and Caching...")
        self.assertIsNotNone(self.db_manager.redis_client, "Redis client should be initialized.")
        self.assertIsInstance(self.db_manager.name_to_uuid_cache, dict, "name_to_uuid_cache should be a dictionary.")
        self.assertIsInstance(self.db_manager.uuid_to_name_cache, dict, "uuid_to_name_cache should be a dictionary.")
        print(" -> Test 1 Passed: Initialization is correct.")

    def test_02_learn_word_creates_correct_plan(self):
        """
        Test 2: Verifies that learn_word generates a valid ExecutionPlan
        for the NLSE.
        """
        print("\nRunning Test 2: learn_word ExecutionPlan...")
        word_to_learn = "Test"
        
        # Call the function we are testing
        self.db_manager.learn_word(word_to_learn)

        # Assert that our mock of _execute_nlse_plan was called exactly once
        self.db_manager._execute_nlse_plan.assert_called_once()
        
        # Get the arguments that were passed to the mock function
        # The first argument is the plan, the second is the operation name
        args, _ = self.db_manager._execute_nlse_plan.call_args
        sent_plan = args[0]

        # Verify the structure of the plan
        self.assertIn("steps", sent_plan)
        self.assertEqual(sent_plan["mode"], "Standard")
        
        # Check that a 'Write' step for the word 'test' was created
        found_word_write = any(
            step.get("Write", {}).get("properties", {}).get("name", {}).get("String") == "test"
            for step in sent_plan["steps"]
        )
        self.assertTrue(found_word_write, "The execution plan must contain a Write step for the word 'Test'.")
        print(" -> Test 2 Passed: learn_word generates a valid plan.")

    def test_03_label_concept_updates_cache_and_plans(self):
        """
        Test 3: Verifies that label_concept correctly updates the internal cache
        and generates a valid ExecutionPlan.
        """
        print("\nRunning Test 3: label_concept Caching and Planning...")
        word = "Socrates"
        concept = "Socrates_Concept"
        
        # First, we must teach it the word so the cache is populated
        self.db_manager.learn_word(word)
        
        # Now, call the function we are testing
        self.db_manager.label_concept(word, concept)

        # Verify the cache was updated correctly
        concept_key = f"concept:{concept.lower()}"
        self.assertIn(concept_key, self.db_manager.name_to_uuid_cache, "Cache must be updated with the new concept key.")
        
        # Verify that an ExecutionPlan was sent
        self.assertTrue(self.db_manager._execute_nlse_plan.called)
        args, _ = self.db_manager._execute_nlse_plan.call_args_list[-1] # Get last call
        sent_plan = args[0]
        
        # Check that a 'Write' step for the concept was created
        found_concept_write = any(
            step.get("Write", {}).get("properties", {}).get("name", {}).get("String") == concept
            for step in sent_plan["steps"]
        )
        self.assertTrue(found_concept_write, "The plan must contain a Write step for the new concept.")
        print(" -> Test 3 Passed: label_concept works correctly.")

    def test_04_learn_fact_handles_unknown_concepts(self):
        """
        Test 4: Verifies that learn_fact correctly raises an error if the
        concepts have not been labeled first.
        """
        print("\nRunning Test 4: learn_fact Error Handling...")
        fact = StructuredTriple(subject="Unknown", relationship="IS_A", object="Thing")
        mock_heart = MagicMock() # Mock the heart orchestrator

        # This should fail because "Unknown" and "Thing" have not been labeled.
        # We use assertRaises to confirm that the expected error occurs.
        with self.assertRaises(ValueError) as context:
            self.db_manager.learn_fact(fact, mock_heart)
        
        self.assertIn("Concept for 'Unknown' or 'Thing' is unknown", str(context.exception))
        print(" -> Test 4 Passed: learn_fact correctly rejects facts with unknown concepts.")

    def test_05_query_fact_builds_correct_plan(self):
        """
        Test 5: Verifies that query_fact uses the cache to find a UUID
        and builds a correct Fetch->Traverse ExecutionPlan.
        """
        print("\nRunning Test 5: query_fact ExecutionPlan...")
        # Manually populate the cache to simulate that the concept "Socrates" has been learned
        socrates_uuid = str(uuid.uuid4())
        self.db_manager.name_to_uuid_cache["concept:socrates"] = socrates_uuid
        
        # Mock the response from the NLSE
        mock_response = {
            "success": True,
            "results": [[{"id": "mock-uuid", "properties": {"name": {"String": "Man"}}}]]
        }
        self.db_manager._execute_nlse_plan.return_value = mock_response

        # Call the function we are testing
        results = self.db_manager.query_fact("Socrates", "IS_A")

        # Verify the plan sent to the NLSE was correct
        self.db_manager._execute_nlse_plan.assert_called_once()
        args, _ = self.db_manager._execute_nlse_plan.call_args
        sent_plan = args[0]

        self.assertEqual(len(sent_plan["steps"]), 2, "Query plan should have two steps (Fetch and Traverse).")
        self.assertEqual(sent_plan["steps"][0]["Fetch"]["id"], socrates_uuid, "The Fetch step must use the correct UUID from the cache.")
        self.assertEqual(sent_plan["steps"][1]["Traverse"]["relationship_type"], "IS_A", "The Traverse step must use the correct relationship.")
        
        # Verify the final result was processed correctly
        self.assertEqual(results, ["Man"])
        print(" -> Test 5 Passed: query_fact builds and processes plans correctly.")

# This allows the test to be run from the command line
if __name__ == '__main__':
    unittest.main()