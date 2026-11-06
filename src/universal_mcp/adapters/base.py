from abc import ABC, abstractmethod
from typing import List, Callable, Any
from universal_mcp.models import DynamicToolDef

class BaseAdapter(ABC):
    @abstractmethod
    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        """Discovers and returns list of (Tool Definition, Callable handler)"""
        pass
