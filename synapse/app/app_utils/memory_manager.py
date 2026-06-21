import logging
from datetime import datetime
from google.cloud import firestore
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages persistent interaction memory using Firestore."""

    def __init__(self, collection_name: str = "agent_memory"):
        self.db = firestore.Client()
        self.collection = self.db.collection(collection_name)

    def save_interaction(self, location_id: str, user_input: str, agent_response: str) -> None:
        """Saves an interaction to Firestore."""
        try:
            doc_ref = self.collection.document()
            doc_ref.set({
                "location_id": location_id,
                "user_input": user_input,
                "agent_response": agent_response,
                "timestamp": datetime.now(),
            })
            logger.info(f"Interaction saved for {location_id}")
        except Exception as e:
            logger.error(f"Failed to save interaction to Firestore: {e}")

    def get_historical_context(self, location_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves recent interactions for a location."""
        try:
            docs = self.collection.where("location_id", "==", location_id)\
                                 .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                                 .limit(limit)\
                                 .stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to retrieve context from Firestore: {e}")
            return []
