"""Natural Language Understanding handler for Carby Studio Bot."""

import logging
import re
from typing import Optional, Dict, List, Tuple
from difflib import get_close_matches

logger = logging.getLogger(__name__)


class Intent:
    """Recognized user intents."""
    PROJECTS = "projects"
    STATUS = "status"
    CONTINUE = "continue"
    HELP = "help"
    CREATE = "create"
    STOP = "stop"
    UNKNOWN = "unknown"


# Expanded keyword lists for better matching
INTENT_KEYWORDS: Dict[str, List[str]] = {
    Intent.PROJECTS: [
        "projects", "project", "list", "my projects", "show projects",
        "what projects", "project list", "view projects", "see projects",
        "all projects", "my work", "current projects", "active projects",
        "what do i have", "what am i working on", "show my stuff"
    ],
    Intent.STATUS: [
        "status", "what's running", "what is running", "whats running",
        "running", "active", "what's happening", "current status",
        "system status", "bot status", "check status", "how's it going",
        "what's going on", "show status", "any updates"
    ],
    Intent.CONTINUE: [
        "continue", "resume", "go back", "keep going", "proceed",
        "where was i", "what was i doing", "continue project",
        "resume project", "back to work", "let's continue", "carry on"
    ],
    Intent.HELP: [
        "help", "how to", "how do i", "what can you do", "commands",
        "what do you do", "instructions", "guide", "tutorial",
        "show help", "help me", "i need help", "how does this work",
        "what are you", "who are you", "what is this"
    ],
    Intent.CREATE: [
        "create", "new", "start", "begin", "init", "initialize",
        "new project", "create project", "start project", "begin project",
        "make new", "add project", "i want to create", "let's start"
    ],
    Intent.STOP: [
        "stop", "cancel", "abort", "halt", "end", "kill",
        "stop agent", "cancel operation", "abort mission", "stop everything"
    ]
}


class NLUHandler:
    """Natural Language Understanding handler."""
    
    def __init__(self, fuzzy_cutoff: float = 0.7):
        """
        Initialize NLU handler.
        
        Args:
            fuzzy_cutoff: Minimum similarity score for fuzzy matching (0-1)
        """
        self.fuzzy_cutoff = fuzzy_cutoff
        self._intent_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile regex patterns for each intent."""
        patterns = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            patterns[intent] = [
                re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                for kw in keywords
            ]
        return patterns
    
    def match_intent(self, text: str) -> Tuple[str, float]:
        """
        Match text to an intent.
        
        Args:
            text: User input text
            
        Returns:
            Tuple of (intent, confidence_score)
        """
        text_lower = text.lower().strip()
        
        # Try exact pattern matching first
        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return intent, 1.0
        
        # Try fuzzy matching for typos
        words = text_lower.split()
        all_keywords = []
        for intent_keywords in INTENT_KEYWORDS.values():
            all_keywords.extend(intent_keywords)
        
        # Check for fuzzy matches on individual words
        for word in words:
            if len(word) < 3:  # Skip short words
                continue
            
            matches = get_close_matches(word, all_keywords, n=1, cutoff=self.fuzzy_cutoff)
            if matches:
                matched_keyword = matches[0]
                # Find which intent this keyword belongs to
                for intent, keywords in INTENT_KEYWORDS.items():
                    if matched_keyword in keywords:
                        # Calculate confidence based on similarity
                        # Simple approximation: longer matches = higher confidence
                        confidence = len(matched_keyword) / max(len(word), len(matched_keyword))
                        return intent, confidence
        
        # Try fuzzy matching on full phrases
        for intent, keywords in INTENT_KEYWORDS.items():
            matches = get_close_matches(text_lower, keywords, n=1, cutoff=self.fuzzy_cutoff)
            if matches:
                return intent, 0.8
        
        return Intent.UNKNOWN, 0.0
    
    def extract_project_name(self, text: str) -> Optional[str]:
        """
        Try to extract a project name from text.
        
        Args:
            text: User input text
            
        Returns:
            Project name if found, None otherwise
        """
        # Common patterns for project references
        patterns = [
            r'(?:project|about|for)\s+["\']?([a-z0-9-]+)["\']?',
            r'["\']?([a-z0-9-]+)["\']?\s+(?:project|status)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        
        return None
    
    def get_suggestions(self, text: str, max_suggestions: int = 3) -> List[str]:
        """
        Get suggested intents for unknown input.
        
        Args:
            text: User input text
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of suggested intent names
        """
        text_lower = text.lower()
        suggestions = []
        
        # Find intents with partial matches
        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                # Check if any word in input matches start of keyword
                for word in text_lower.split():
                    if len(word) >= 3 and keyword.startswith(word):
                        suggestions.append(intent)
                        break
                if intent in suggestions:
                    break
        
        # Remove duplicates and limit
        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        
        return unique[:max_suggestions]
    
    def format_suggestions(self, suggestions: List[str]) -> str:
        """
        Format suggestions for display.
        
        Args:
            suggestions: List of intent names
            
        Returns:
            Formatted suggestion text
        """
        if not suggestions:
            return "Try: 📋 Projects, 📊 Status, or ❓ Help"
        
        intent_labels = {
            Intent.PROJECTS: "📋 View Projects",
            Intent.STATUS: "📊 Check Status",
            Intent.CONTINUE: "🔄 Continue Last",
            Intent.HELP: "❓ Get Help",
            Intent.CREATE: "➕ Create Project",
            Intent.STOP: "🛑 Stop Agent"
        }
        
        labels = [intent_labels.get(s, s) for s in suggestions]
        return "Did you mean: " + ", ".join(labels) + "?"


# Global NLU handler instance
_nlu_handler: Optional[NLUHandler] = None


def get_nlu_handler() -> NLUHandler:
    """Get or create global NLU handler."""
    global _nlu_handler
    if _nlu_handler is None:
        _nlu_handler = NLUHandler()
    return _nlu_handler


def match_intent(text: str) -> Tuple[str, float]:
    """Convenience function to match intent."""
    return get_nlu_handler().match_intent(text)


def extract_project_name(text: str) -> Optional[str]:
    """Convenience function to extract project name."""
    return get_nlu_handler().extract_project_name(text)
