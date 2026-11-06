import os
import re
from typing import Dict, Any, Union

class EnvInterpolator:
    """
    Interpolates environment variables in the format ${VAR_NAME} or ${VAR_NAME:-default_value}
    inside configuration strings, dictionaries, lists and headers.
    """
    PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")

    @classmethod
    def interpolate_str(cls, text: str) -> str:
        if not isinstance(text, str):
            return text

        def replace_match(match):
            var_name = match.group(1)
            default_val = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default_val)

        return cls.PATTERN.sub(replace_match, text)

    @classmethod
    def interpolate(cls, data: Any) -> Any:
        if isinstance(data, str):
            return cls.interpolate_str(data)
        elif isinstance(data, dict):
            return {k: cls.interpolate(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.interpolate(item) for item in data]
        return data
