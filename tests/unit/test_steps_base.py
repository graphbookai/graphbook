from graphbook.core.steps.base import Step, SourceStep, GeneratorSourceStep, Split, Copy
from unittest.mock import MagicMock


class TestStepBase:
    """Test the base Step class functionality."""

    def test_basic_step_instantiation(self):
        """Test basic instantiation of a Step."""
        step = Step()
        assert step.id is None
        assert step.item_key is None

    def test_step_with_item_key(self):
        """Test instantiation with an item_key."""
        step = Step(item_key="test_key")
        assert step.item_key == "test_key"

    def test_step_call_with_data(self):
        """Test the __call__ method with data."""
        step = Step()

        # Create a mock for on_data method
        step.on_data = MagicMock()
        step.on_after_item = MagicMock()

        test_data = {"key": "value"}
        result = step(test_data)

        # Verify method calls
        step.on_data.assert_called_once_with(test_data)
        step.on_after_item.assert_called_once_with(test_data)

        # Check result structure
        assert "out" in result
        assert result["out"][0] == test_data

    def test_step_with_item_key_call(self):
        """Test calling a step with an item_key."""
        step = Step(item_key="item")

        # Create mocks for methods
        step.on_data = MagicMock()
        step.on_item = MagicMock()
        step.on_after_item = MagicMock()

        test_data = {"item": "test_item"}
        step(test_data)

        # Verify method calls
        step.on_data.assert_called_once_with(test_data)
        step.on_item.assert_called_once_with("test_item", test_data)
        step.on_after_item.assert_called_once_with(test_data)

    def test_route_method(self):
        """Test the route method with custom routing."""

        class CustomRouteStep(Step):
            def route(self, data):
                if data.get("route_to") == "custom":
                    return "custom_route"
                return "default_route"

        step = CustomRouteStep()

        # Test routing to custom route
        custom_data = {"route_to": "custom"}
        result = step(custom_data)
        assert "custom_route" in result
        assert result["custom_route"][0] == custom_data

        # Test routing to default route
        default_data = {"route_to": "other"}
        result = step(default_data)
        assert "default_route" in result
        assert result["default_route"][0] == default_data

    def test_step_all_method(self):
        """Test the all method for processing multiple data items."""

        class TestStep(Step):
            def route(self, data):
                print(data)
                if data["value"] > 0:
                    return {"positive": [data]}
                else:
                    return {"zero_or_negative": [data]}

        step = TestStep()
        data_list = [{"value": 1}, {"value": -1}, {"value": 0}, {"value": 2}]

        result = step.all(data_list)

        # Should have both output keys
        assert "positive" in result
        assert "zero_or_negative" in result

        # Check counts
        assert len(result["positive"]) == 2  # 1, 2
        assert len(result["zero_or_negative"]) == 2  # -1, 0


class TestSourceSteps:
    """Test the source step classes."""

    def test_source_step(self):
        """Test the SourceStep class."""

        class TestSourceStep(SourceStep):
            def load(self):
                return {"out": [{"value": 1}, {"value": 2}, {"value": 3}]}

        step = TestSourceStep()
        result = step()

        assert "out" in result
        assert len(result["out"]) == 3
        assert result["out"][0]["value"] == 1
        assert result["out"][1]["value"] == 2
        assert result["out"][2]["value"] == 3

    def test_generator_source_step(self):
        """Test the GeneratorSourceStep class."""

        class TestGeneratorSourceStep(GeneratorSourceStep):
            def load(self):
                for i in range(3):
                    yield {"out": [{"value": i}]}

        step = TestGeneratorSourceStep()

        # First call
        result1 = step()
        assert "out" in result1
        assert result1["out"][0]["value"] == 0

        # Second call
        result2 = step()
        assert "out" in result2
        assert result2["out"][0]["value"] == 1

        # Third call
        result3 = step()
        assert "out" in result3
        assert result3["out"][0]["value"] == 2

        # Fourth call (generator exhausted)
        result4 = step()
        assert result4 == {}

        # Test on_clear to reset the generator
        step.on_clear()
        result_after_clear = step()
        assert "out" in result_after_clear
        assert result_after_clear["out"][0]["value"] == 0


class TestBuiltInSteps:
    """Test the built-in Step subclasses."""

    def test_split_step(self):
        """Test the Split step."""
        split_fn = """def split(data):
            return data["value"] > 0
        """

        split_step = Split(split_fn=split_fn)

        # Test positive value (should go to "A")
        positive_data = {"value": 5}
        result = split_step(positive_data)
        assert "A" in result
        assert result["A"][0] == positive_data
        assert "B" not in result

        # Test negative value (should go to "B")
        negative_data = {"value": -5}
        result = split_step(negative_data)
        assert "B" in result
        assert result["B"][0] == negative_data
        assert "A" not in result

        # Test zero value (should go to "B")
        zero_data = {"value": 0}
        result = split_step(zero_data)
        assert "B" in result
        assert result["B"][0] == zero_data
        assert "A" not in result

    def test_copy_step(self):
        """Test the Copy step."""
        copy_step = Copy()

        # Test with simple data
        test_data = {"value": 42}
        result = copy_step(test_data)

        # Should have both A and B outputs
        assert "A" in result
        assert "B" in result

        # A should be the original, B should be a deep copy
        assert result["A"][0] == test_data
        assert result["B"][0] == test_data
        assert result["A"][0] is test_data  # Same object
        assert result["B"][0] is not test_data  # Different object

        # Modify the original, should not affect the copy
        test_data["value"] = 100
        assert result["A"][0]["value"] == 100
        assert result["B"][0]["value"] == 42
