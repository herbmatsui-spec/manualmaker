"""
Output Plugin Architecture (Step 11)
Defines unified interface for output generators and a registry for plugin management.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseOutputGenerator(ABC):
    """Abstract Base Class for output format generators"""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format (e.g. 'pdf', 'docx', 'audio', 'diagram')"""
        pass

    @abstractmethod
    def generate(self, summary_result: Any, output_dir: Path, filename_prefix: str, **kwargs) -> Optional[Path]:
        """Generate output file and return path to created artifact"""
        pass


class PluginRegistry:
    """Registry to register, discover, and invoke output plugins"""

    _plugins: Dict[str, BaseOutputGenerator] = {}

    @classmethod
    def register(cls, plugin: BaseOutputGenerator) -> None:
        """Register a plugin instance"""
        fmt = plugin.format_name.lower()
        cls._plugins[fmt] = plugin
        logger.info(f"PluginRegistry: Registered plugin for format '{fmt}'")

    @classmethod
    def get_plugin(cls, format_name: str) -> Optional[BaseOutputGenerator]:
        """Get plugin for a specific format"""
        return cls._plugins.get(format_name.lower())

    @classmethod
    def list_formats(cls) -> List[str]:
        """List registered format names"""
        return list(cls._plugins.keys())

    @classmethod
    def generate_outputs(
        cls,
        summary_result: Any,
        output_dir: Path,
        filename_prefix: str,
        enabled_formats: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Path]:
        """Generate all enabled output formats"""
        results = {}
        formats = enabled_formats or cls.list_formats()

        for fmt in formats:
            plugin = cls.get_plugin(fmt)
            if plugin:
                try:
                    out_path = plugin.generate(summary_result, output_dir, filename_prefix, **kwargs)
                    if out_path:
                        results[fmt] = out_path
                except Exception as e:
                    logger.error(f"PluginRegistry: Failed to generate '{fmt}': {e}")
            else:
                logger.warning(f"PluginRegistry: No plugin registered for format '{fmt}'")

        return results
