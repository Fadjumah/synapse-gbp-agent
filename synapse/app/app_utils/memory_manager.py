import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages persistent interaction memory using Firestore or local fallback."""

    def __init__(self, collection_name: str = "agent_memory"):
        self.enabled = False
        self.db = None
        self.collection = None
        
        if not FIRESTORE_AVAILABLE:
            logger.warning("Firestore library not installed. Memory features disabled.")
            return

        # Check for service account or explicit credentials to avoid metadata server timeouts
        # GOOGLE_APPLICATION_CREDENTIALS is the standard, but we also allow FIRESTORE_PROJECT_ID override
        project_id = os.getenv("FIRESTORE_PROJECT_ID")
        
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv("FIREBASE_SERVICE_ACCOUNT") and not project_id:
            logger.warning("No Firestore credentials or project ID found in environment. Memory features disabled to avoid timeouts.")
            return

        try:
            # Set a short timeout for initialization if possible
            self.db = firestore.Client(project=project_id)
            self.collection = self.db.collection(collection_name)
            
            logger.info(f"Attempting to connect to Firestore project: {self.db.project}")
            
            # Simple check to see if we can actually reach Firestore
            # This avoids noisy 403s later if the API is disabled
            try:
                list(self.collection.limit(1).stream(timeout=2))
                self.enabled = True
                logger.info(f"Firestore MemoryManager initialized successfully for project: {self.db.project}")
            except Exception as e:
                logger.warning(f"Firestore API check failed for project {self.db.project}: {e}. Memory features will be disabled.")
                self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Client: {e}")
            self.enabled = False

    def save_interaction(self, location_id: str, user_input: str, agent_response: str) -> None:
        """Saves an interaction to Firestore."""
        if not self.enabled:
            return
            
        try:
            doc_ref = self.collection.document()
            doc_ref.set({
                "location_id": location_id,
                "user_input": user_input,
                "agent_response": agent_response,
                "timestamp": datetime.now(),
            }, timeout=5) # Add a timeout
            logger.info(f"Interaction saved for {location_id}")
        except Exception as e:
            logger.error(f"Failed to save interaction to Firestore: {e}")

    def get_historical_context(self, location_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves recent interactions for a location."""
        if not self.enabled:
            return []
            
        try:
            docs = self.collection.where("location_id", "==", location_id)\
                                 .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                                 .limit(limit)\
                                 .stream(timeout=5) # Add a timeout
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to retrieve context from Firestore: {e}")
            return []
