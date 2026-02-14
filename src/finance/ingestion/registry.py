"""Registry for ingestion parsers."""
from typing import Dict, Type, List, Any
from finance.ingestion.base import BaseParser

class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a parser."""
        def decorator(parser_cls: Type[BaseParser]):
            cls._parsers[name] = parser_cls
            return parser_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseParser]:
        """Get a parser class by name."""
        return cls._parsers[name]

    @classmethod
    def list_parsers(cls, include_extended_metadata: bool = False) -> List[Dict[str, Any]]:
        """List all available parsers with metadata.

        Args:
            include_extended_metadata: If True, include extended metadata
                                       (example_input, field_mappings, etc.)

        Returns:
            List of parser metadata dictionaries
        """
        parsers = []
        for name, parser in cls._parsers.items():
            if include_extended_metadata and hasattr(parser, 'get_metadata'):
                # Get full metadata from parser
                metadata = {
                    "name": name,
                    **parser.get_metadata(parser),  # Call as unbound method
                }
            else:
                # Basic metadata only
                metadata = {
                    "name": name,
                    "description": parser.description,
                    "supported_formats": getattr(parser, "supported_formats", []),
                    "required_args": getattr(parser, "required_args", []),
                }
            parsers.append(metadata)
        return parsers

    @classmethod
    def get_parser_metadata(cls, name: str) -> Dict[str, Any]:
        """Get full metadata for a specific parser.

        Args:
            name: Parser name

        Returns:
            Dictionary with all parser metadata

        Raises:
            KeyError: If parser not found
        """
        parser = cls.get(name)
        if hasattr(parser, 'get_metadata'):
            return {
                "name": name,
                **parser.get_metadata(parser),  # Call as unbound method
            }
        else:
            return {
                "name": name,
                "description": parser.description,
                "supported_formats": getattr(parser, "supported_formats", []),
                "required_args": getattr(parser, "required_args", []),
            }
