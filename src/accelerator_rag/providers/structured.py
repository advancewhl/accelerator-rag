"""Schema-directed compatibility for OpenAI-compatible function arguments.

Only redundant containers are removed; field values, unknown keys and invalid
JSON are never repaired or guessed. Domain validation remains strict.
"""

from copy import deepcopy


def inline_schema(schema):
    schema = deepcopy(schema)
    definitions = schema.pop("$defs", {})

    def expand(node):
        if isinstance(node, list):
            return [expand(item) for item in node]
        if isinstance(node, dict):
            if "$ref" in node:
                return expand(definitions[node["$ref"].split("/")[-1]])
            return {key: expand(value) for key, value in node.items()}
        return node

    return expand(schema)


def normalize_tool_arguments(value, schema):
    """Unwrap e.g. items:[{items:[...]}] when items is not an item field."""
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        result = dict(value)
        for key, child_schema in properties.items():
            if key not in result:
                continue
            child = result[key]
            if child_schema.get("type") == "array":
                item_properties = child_schema.get("items", {}).get("properties", {})
                for _ in range(2):
                    if (
                        key not in item_properties
                        and isinstance(child, list)
                        and len(child) == 1
                        and isinstance(child[0], dict)
                        and set(child[0]) == {key}
                        and isinstance(child[0][key], list)
                    ):
                        child = child[0][key]
                    else:
                        break
            result[key] = normalize_tool_arguments(child, child_schema)
        return result
    if isinstance(value, list):
        return [
            normalize_tool_arguments(item, schema.get("items", {})) for item in value
        ]
    return value
