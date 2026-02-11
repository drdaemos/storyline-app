class SchemaValidationError(ValueError):
    """Raised when value does not match a JSON-schema-like contract."""


def validate_schema(value: object, schema: dict[str, object], path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        _validate_object(value, schema, path)
    elif schema_type == "array":
        _validate_array(value, schema, path)
    elif schema_type == "integer":
        _validate_integer(value, schema, path)
    elif schema_type == "number":
        _validate_number(value, schema, path)
    elif schema_type == "string":
        _validate_string(value, schema, path)
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected boolean")
    elif schema_type is None:
        return
    else:
        raise SchemaValidationError(f"{path}: unsupported schema type '{schema_type}'")


def _validate_object(value: object, schema: dict[str, object], path: str) -> None:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path}: expected object")

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    additional_properties = schema.get("additionalProperties", True)

    if not isinstance(required, list):
        raise SchemaValidationError(f"{path}: 'required' must be an array")
    for key in required:
        if key not in value:
            raise SchemaValidationError(f"{path}: missing required property '{key}'")

    if not isinstance(properties, dict):
        raise SchemaValidationError(f"{path}: 'properties' must be an object")
    for key, item in value.items():
        prop_schema = properties.get(key)
        if isinstance(prop_schema, dict):
            validate_schema(item, prop_schema, f"{path}.{key}")
        elif not additional_properties:
            raise SchemaValidationError(f"{path}: unknown property '{key}' not allowed")


def _validate_array(value: object, schema: dict[str, object], path: str) -> None:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path}: expected array")
    min_items = schema.get("minItems")
    max_items = schema.get("maxItems")
    if min_items is not None and len(value) < min_items:
        raise SchemaValidationError(f"{path}: expected at least {min_items} items")
    if max_items is not None and len(value) > max_items:
        raise SchemaValidationError(f"{path}: expected at most {max_items} items")
    item_schema = schema.get("items")
    if item_schema:
        for index, item in enumerate(value):
            validate_schema(item, item_schema, f"{path}[{index}]")


def _validate_integer(value: object, schema: dict[str, object], path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(f"{path}: expected integer")
    minimum = schema.get("minimum", schema.get("min"))
    maximum = schema.get("maximum", schema.get("max"))
    if minimum is not None and value < minimum:
        raise SchemaValidationError(f"{path}: expected >= {minimum}")
    if maximum is not None and value > maximum:
        raise SchemaValidationError(f"{path}: expected <= {maximum}")


def _validate_number(value: object, schema: dict[str, object], path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{path}: expected number")
    minimum = schema.get("minimum", schema.get("min"))
    maximum = schema.get("maximum", schema.get("max"))
    if minimum is not None and value < minimum:
        raise SchemaValidationError(f"{path}: expected >= {minimum}")
    if maximum is not None and value > maximum:
        raise SchemaValidationError(f"{path}: expected <= {maximum}")


def _validate_string(value: object, schema: dict[str, object], path: str) -> None:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{path}: expected string")
    min_len = schema.get("minLength")
    max_len = schema.get("maxLength")
    if min_len is not None and len(value) < min_len:
        raise SchemaValidationError(f"{path}: expected minLength {min_len}")
    if max_len is not None and len(value) > max_len:
        raise SchemaValidationError(f"{path}: expected maxLength {max_len}")
