import logging
import json
from typing import List, Dict, Any

from db_interface import db_manager

# Note: numpy and sklearn will be imported within methods
# to handle potential import errors gracefully if not installed.

logger = logging.getLogger(__name__)

# Corrected: PROTOTYPE_DB is not used in this file's logic
# PROTOTYPE_DB = {} 

class EmotionCrystallizer:
    """
    An autonomous agent that analyzes the log of raw 'Illusions' to find
    recurring patterns and form stable 'Emotion Prototypes'. This is the
    bridge between raw sensation and recognizable feeling.
    """
    def __init__(self, db_manager_instance=db_manager):
        self.db_manager = db_manager_instance
        logger.info("Emotion Crystallizer initialized.")
    
    def fetch_unlabeled_illusions(self) -> List[Dict[str, Any]]:
        """
        Connects to Redis and retrieves the entire log of raw illusions.
        This is the raw data for our pattern recognition.
        """
        illusions = []
        try:
            while True:
                illusion_json = self.db_manager.redis_client.rpop("illusion_log")
                if illusion_json is None:
                    break 
                
                illusion_data = json.loads(illusion_json)
                illusions.append(illusion_data)
        
        except Exception as e:
            logger.error(f"Crystallizer failed to fetch illusions from Redis: {e}")
            return []

        if illusions:
            logger.info(f"Crystallizer fetched {len(illusions)} new illusions for analysis.")
        
        return illusions
    
    # Corrected: Moved these functions inside the class
    def _illusions_to_vectors(self, illusions: List[Dict[str, Any]]) -> 'numpy.ndarray':
        """Helper to convert a list of illusion dicts into a 2D NumPy array."""
        import numpy as np
        
        if not illusions: # Handle empty list
            return np.array([])

        feature_keys = sorted(illusions[0]['physio_state_signature'].keys())
        
        vectors = []
        for illusion in illusions:
            vector = [illusion['physio_state_signature'].get(key, 0.0) for key in feature_keys]
            vectors.append(vector)
            
        return np.array(vectors)

    def _cluster_illusions(self, illusions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Groups illusions with similar physiological signatures into clusters.
        """
        if not illusions or len(illusions) < 2:
            return []

        try:
            from sklearn.cluster import DBSCAN
            import numpy as np
        except ImportError:
            logger.error("Crystallizer cannot cluster: scikit-learn or numpy not installed.")
            return []
            
        vectors = self._illusions_to_vectors(illusions)
        if vectors.size == 0: # Handle empty vectors after conversion
            return []

        # DBSCAN parameters might need tuning for real-world data
        dbscan = DBSCAN(eps=0.5, min_samples=2) # eps: max distance, min_samples: min points in cluster
        clusters = dbscan.fit_predict(vectors)

        num_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
        logger.info(f"Crystallizer found {num_clusters} potential emotion clusters.")
        
        grouped_illusions = []
        for cluster_id in range(num_clusters):
            cluster = [
                illusion for i, illusion in enumerate(illusions) 
                if clusters[i] == cluster_id
            ]
            grouped_illusions.append(cluster)
        
        return grouped_illusions

    def _create_prototype_from_cluster(self, cluster: List[Dict[str, Any]]):
        """
        If a cluster is large enough, this creates a stable Emotion Prototype from it.
        """
        import uuid
        import numpy as np
        from collections import Counter
        import time # For time.time()

        CRYSTALLIZE_THRESHOLD = 5 

        if len(cluster) < CRYSTALLIZE_THRESHOLD:
            return

        logger.info(f"Found a significant cluster with {len(cluster)} instances. Attempting to crystallize.")
        
        vectors = self._illusions_to_vectors(cluster)
        average_vector = np.mean(vectors, axis=0)
        
        feature_keys = sorted(cluster[0]['physio_state_signature'].keys())
        average_signature = {key: round(val, 2) for key, val in zip(feature_keys, average_vector)}

        trigger_events = [illusion['event'] for illusion in cluster]
        common_triggers = [item for item, count in Counter(trigger_events).most_common()]

        prototype = {
            "prototype_id": str(uuid.uuid4()),
            "name": None, 
            "average_signature": average_signature,
            "common_triggers": common_triggers,
            "crystallization_timestamp": int(time.time()), # Using standard time.time()
            "occurrence_count": len(cluster)
        }
        
        self.db_manager.save_emotion_prototype(prototype)

    def run(self):
        """
        The main orchestration method for the agent. This is the entry point
        for the periodic background task.
        """
        illusions = self.fetch_unlabeled_illusions()

        if not illusions:
            logger.info("Crystallizer: No new illusions to process.")
            return

        clusters = self._cluster_illusions(illusions)
        
        if not clusters:
            logger.info(f"Crystallizer: Processed {len(illusions)} illusions, but no significant patterns found.")
            return

        for cluster in clusters:
            self._create_prototype_from_cluster(cluster)
            
        logger.info(f"Crystallizer: Finished processing run for {len(illusions)} illusions.")