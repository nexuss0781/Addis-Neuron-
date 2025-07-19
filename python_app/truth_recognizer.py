import requests
from bs4 import BeautifulSoup
import spacy
from typing import List, Optional
import logging

from models import StructuredTriple

# Setup logging
logger = logging.getLogger(__name__)

class TruthRecognizer:
    """
    Represents the brain's ability to interface with the external world (e.g., the web)
    to gather new information and parse it into a learnable format.
    """
    def __init__(self):
        try:
            # Load the small English model for spaCy
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
            self.nlp = None

    def search_and_extract_text(self, topic: str) -> Optional[str]:
        """
        Performs a simple web search (on Wikipedia) and extracts the text content.
        """
        search_url = f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
        headers = {'User-Agent': 'AgileMind/0.1 (agile.mind.project; cool@example.com)'}
        
        logger.info(f"TruthRecognizer: Searching for topic '{topic}' at {search_url}")
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            # Find the main content div and extract text from paragraphs
            content_div = soup.find(id="mw-content-text")
            if not content_div:
                return None
            
            paragraphs = content_div.find_all('p', limit=5) # Limit to first 5 paragraphs
            return " ".join([p.get_text() for p in paragraphs])
        except requests.RequestException as e:
            logger.error(f"Could not fetch web content for topic '{topic}': {e}")
            return None

    def text_to_triples(self, text: str) -> List[StructuredTriple]:
        """
        A simplified NLP function to extract Subject-Verb-Object triples from text.
        """
        if not self.nlp or not text:
            return []

        doc = self.nlp(text)
        triples = []
        
        for sent in doc.sents:
            # A very basic rule-based extraction
            subjects = [tok for tok in sent if "subj" in tok.dep_]
            objects = [tok for tok in sent if "obj" in tok.dep_ or "attr" in tok.dep_]
            
            if subjects and objects:
                subject_text = subjects[0].text
                object_text = objects[0].text
                verb_text = sent.root.lemma_.upper() # Use lemma of the root verb
                
                # Create a triple if we have all parts. This is highly simplified.
                if subject_text and verb_text and object_text:
                    # To-Do: A much more sophisticated logic to map verb to relationship type
                    relationship = "HAS_VERB_ACTION" # Generic relationship for now
                    if verb_text == 'BE':
                        relationship = 'IS_A'

                    triples.append(StructuredTriple(
                        subject=subject_text,
                        relationship=relationship,
                        object=object_text
                    ))
        
        logger.info(f"TruthRecognizer: Extracted {len(triples)} triples from text.")
        return triples

    def investigate(self, topic: str) -> List[StructuredTriple]:
        """
        The main public method that orchestrates the entire process.
        """
        text_content = self.search_and_extract_text(topic)
        if text_content:
            return self.text_to_triples(text_content)
        return []

# Singleton instance for easy access
truth_recognizer = TruthRecognizer()