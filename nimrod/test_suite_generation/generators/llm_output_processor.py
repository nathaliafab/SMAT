import re
from typing import List, Optional
from abc import ABC, abstractmethod


class OutputSanitizationRule(ABC):
    """Abstract base class for output sanitization rules."""

    @abstractmethod
    def apply(self, output: str) -> str:
        """Apply the sanitization rule to the output."""
        pass


class RemoveThinkTagsRule(OutputSanitizationRule):
    """Removes content between <think> tags."""

    def apply(self, output: str) -> str:
        return re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL)


class ExtractCodeBlocksRule(OutputSanitizationRule):
    """Extracts content from code blocks (``` markers)."""

    def apply(self, output: str) -> str:
        matches = re.findall(r'```(?:\w+)?\n?(.*?)```', output, flags=re.DOTALL)
        return '\n'.join(matches).strip()


class RemoveNumberedLinesRule(OutputSanitizationRule):
    """Removes lines starting with 'number. <text>' pattern."""

    def apply(self, output: str) -> str:
        return re.sub(r"^\d+\.\s.*$", "", output, flags=re.MULTILINE)


class ExtractFromAnnotationsRule(OutputSanitizationRule):
    """Keeps only content starting from the first annotation marker."""

    def __init__(self, markers: Optional[List[str]] = None):
        self.markers = markers or ["@Before", "@BeforeClass", "@Test"]

    def apply(self, output: str) -> str:
        index = min(
            (output.find(marker) for marker in self.markers if marker in output), 
            default=-1
        )
        return output[index:] if index != -1 else output


class LLMOutputProcessor:
    """
    Processes and sanitizes LLM outputs using configurable rules.
    
    This class provides a flexible framework for cleaning LLM outputs
    by applying a series of sanitization rules in sequence.
    """

    def __init__(self) -> None:
        self._rules: List[OutputSanitizationRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load the default set of sanitization rules."""
        self._rules = [
            RemoveThinkTagsRule(),
            ExtractCodeBlocksRule(),
            RemoveNumberedLinesRule(),
            ExtractFromAnnotationsRule()
        ]

    def add_rule(self, rule: OutputSanitizationRule) -> None:
        """Add a custom sanitization rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_type: type) -> None:
        """Remove all rules of the specified type."""
        self._rules = [rule for rule in self._rules if not isinstance(rule, rule_type)]

    def clear_rules(self) -> None:
        """Remove all sanitization rules."""
        self._rules.clear()

    def process(self, output: str) -> str:
        """
        Process the LLM output by applying all sanitization rules in sequence.
        
        Args:
            output: The raw output from the LLM model
            
        Returns:
            The processed and sanitized output
        """
        processed_output = output

        for rule in self._rules:
            try:
                processed_output = rule.apply(processed_output)
            except Exception as e:
                # Log the error but continue processing with other rules
                import logging
                logging.warning(f"Error applying rule {rule.__class__.__name__}: {e}")

        return processed_output

    def get_active_rules(self) -> List[str]:
        """Get the names of currently active rules."""
        return [rule.__class__.__name__ for rule in self._rules]