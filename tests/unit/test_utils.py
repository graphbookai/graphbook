import pytest
from graphbook.core.utils import (
    transform_function_string,
    is_batchable,
    transform_json_log,
    image,
    ExecutionContext,
)
from PIL import Image as PILImage


class TestTransformFunctionString:
    """Test the function string transformation utility."""

    def test_basic_function_transform(self):
        """Test basic function transformation from string to callable."""
        func_str = """def add(a, b):
            return a + b"""

        func = transform_function_string(func_str)
        assert callable(func)
        assert func(3, 4) == 7

    def test_complex_function_transform(self):
        """Test transformation of a more complex function with multiple statements."""
        func_str = """def process_data(data):
            result = {}
            for key, value in data.items():
                result[key] = value * 2
            return result"""

        func = transform_function_string(func_str)
        assert callable(func)
        test_data = {"a": 1, "b": 2}
        assert func(test_data) == {"a": 2, "b": 4}

    def test_invalid_function_string(self):
        """Test that an exception is raised for invalid function strings."""
        func_str = "not a function"
        with pytest.raises(ValueError):
            transform_function_string(func_str)


class TestIsBatchable:
    """Test the is_batchable utility function."""

    def test_list_is_batchable(self):
        """Test that lists are identified as batchable."""
        assert is_batchable([1, 2, 3]) is True

    def test_non_batchable_types(self):
        """Test that non-batchable types are correctly identified."""
        assert is_batchable("string") is False
        assert is_batchable(123) is False
        assert is_batchable({"key": "value"}) is False


class TestTransformJsonLog:
    """Test the JSON log transformation utility."""

    def test_simple_types(self):
        """Test that simple types are returned unchanged."""
        assert transform_json_log(123) == 123
        assert transform_json_log("test") == "test"
        assert transform_json_log(True) is True

    def test_dict_transform(self):
        """Test that dictionaries are transformed correctly."""
        test_dict = {"a": 1, "b": "test"}
        assert transform_json_log(test_dict) == test_dict

    def test_list_transform(self):
        """Test that lists are transformed correctly."""
        test_list = [1, "test", True]
        assert transform_json_log(test_list) == test_list

    def test_bytes_transform(self):
        """Test that bytes are transformed to a descriptive string."""
        test_bytes = b"test bytes"
        result = transform_json_log(test_bytes)
        assert isinstance(result, str)
        assert "bytes of length" in result

    def test_pil_image_transform(self):
        """Test that PIL Images are transformed to a descriptive string."""
        # Create a small test image
        test_image = PILImage.new("RGB", (10, 10))
        result = transform_json_log(test_image)
        assert isinstance(result, str)
        assert "PIL Image of size" in result


class TestImageHelper:
    """Test the image helper function."""

    def test_with_path(self):
        """Test the image helper with a file path."""
        result = image("path/to/image.jpg")
        assert isinstance(result, dict)
        assert result["type"] == "image"
        assert result["value"] == "path/to/image.jpg"

    def test_with_pil_image(self):
        """Test the image helper with a PIL Image."""
        test_image = PILImage.new("RGB", (10, 10))
        result = image(test_image)
        assert isinstance(result, dict)
        assert result["type"] == "image"
        assert result["value"] == test_image

    def test_invalid_input(self):
        """Test that the function raises an assertion error for invalid inputs."""
        with pytest.raises(AssertionError):
            image(123)

        with pytest.raises(AssertionError):
            image(["not", "an", "image"])


class TestExecutionContext:
    """Test the ExecutionContext class."""

    def test_get_empty_context(self):
        """Test that getting an empty context returns an empty dict."""
        context = ExecutionContext.get_context()
        assert isinstance(context, dict)

    def test_update_and_get(self):
        """Test updating and retrieving values from the context."""
        ExecutionContext.update(test_key="test_value")
        assert ExecutionContext.get("test_key") == "test_value"

    def test_get_with_default(self):
        """Test getting a non-existent key with a default value."""
        assert ExecutionContext.get("non_existent", "default") == "default"
