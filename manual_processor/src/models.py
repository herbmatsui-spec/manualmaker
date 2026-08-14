"""
Common Data Models
Shared data classes used across the application
"""

from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Section:
    """Section within a document"""
    title: str
    content: str
    subsections: List['Section'] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {'title': self.title, 'content': self.content}
