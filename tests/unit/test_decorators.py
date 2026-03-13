from graphbook.core.decorators import (
    step,
    param,
    source,
    output,
    resource,
    event,
)
from graphbook.core import steps


class TestStepDecorators:
    """Test the step decorator functionality."""

    def test_basic_step_decorator(self):
        """Test that a basic step can be created with the step decorator."""

        @step("Test/BasicStep")
        def basic_step(ctx, data):
            data["processed"] = True
            return data

        assert basic_step.__name__ == "BasicStep"
        assert basic_step.Category == "Test"

        # Test the step functionality
        step_instance = basic_step()
        test_data = {}
        result = step_instance(test_data)
        assert "out" in result
        assert result["out"][0]["processed"] is True

    def test_step_with_parameters(self):
        """Test that parameters can be added to steps."""

        @step("Test/ParamStep")
        @param("value", "number", default=42, description="Test value")
        def param_step(ctx, data):
            data["value"] = ctx.value
            return data

        assert param_step.__name__ == "ParamStep"

        # Check parameter metadata
        assert "value" in param_step.Parameters
        assert param_step.Parameters["value"]["default"] == 42
        assert param_step.Parameters["value"]["description"] == "Test value"

        # Test the step with default parameter
        step_instance = param_step()
        test_data = {}
        result = step_instance(test_data)
        assert result["out"][0]["value"] == 42

        # Test the step with custom parameter
        step_instance = param_step(value=100)
        test_data = {}
        result = step_instance(test_data)
        assert result["out"][0]["value"] == 100

    def test_source_decorator(self):
        """Test that the source decorator creates a source step."""

        @step("Test/SourceStep")
        @source()
        def source_step(ctx):
            for i in range(3):
                yield {"out": [{"value": i}]}

        assert source_step.__name__ == "SourceStep"

        # Check that it's a source step
        assert issubclass(source_step, steps.GeneratorSourceStep)

        # Test the source step functionality
        step_instance = source_step()
        result1 = step_instance()
        assert result1["out"][0]["value"] == 0

        result2 = step_instance()
        assert result2["out"][0]["value"] == 1

        result3 = step_instance()
        assert result3["out"][0]["value"] == 2

        result4 = step_instance()
        assert result4 == {}  # Generator exhausted

    def test_output_decorator(self):
        """Test that the output decorator sets custom output slots."""

        @step("Test/OutputStep", event="route")
        @output("success", "failure")
        def output_step(ctx, data):
            if data.get("success", False):
                return "success"
            return "failure"

        assert output_step.__name__ == "OutputStep"

        # Check output slots
        assert output_step.Outputs == ["success", "failure"]

        # Test routing to success
        step_instance = output_step()
        success_data = {"success": True}
        result = step_instance(success_data)
        assert "success" in result
        assert result["success"][0] == success_data
        assert "failure" not in result

        # Test routing to failure
        failure_data = {"success": False}
        result = step_instance(failure_data)
        assert "failure" in result
        assert result["failure"][0] == failure_data
        assert "success" not in result

    def test_event_decorator(self):
        """Test that the event decorator adds custom event handlers."""

        def init_handler(ctx, **kwargs):
            ctx.initialized = True

        def clear_handler(ctx):
            ctx.initialized = False

        @step("Test/EventStep")
        @event("__init__", init_handler)
        @event("on_clear", clear_handler)
        def event_step(ctx, data):
            data["initialized"] = ctx.initialized
            return data

        assert event_step.__name__ == "EventStep"

        # Test events
        step_instance = event_step()
        assert step_instance.initialized is True

        test_data = {}
        result = step_instance(test_data)
        assert result["out"][0]["initialized"] is True

        step_instance.on_clear()
        assert step_instance.initialized is False


class TestResourceDecorators:
    """Test the resource decorator functionality."""

    def test_basic_resource_decorator(self):
        """Test that a basic resource can be created with the resource decorator."""

        @resource("Test/SimpleResource")
        def simple_resource(ctx):
            return "resource_value"

        assert simple_resource.__name__ == "SimpleResource"
        assert simple_resource.Category == "Test"

        # Test the resource value
        resource_instance = simple_resource()
        assert resource_instance.value() == "resource_value"

    def test_resource_with_parameters(self):
        """Test that parameters can be added to resources."""

        @resource("Test/ParamResource")
        @param("name", "string", default="default_name", description="Resource name")
        def param_resource(ctx):
            return f"Resource: {ctx.name}"

        assert param_resource.__name__ == "ParamResource"

        # Check parameter metadata
        assert "name" in param_resource.Parameters
        assert param_resource.Parameters["name"]["default"] == "default_name"
        assert param_resource.Parameters["name"]["description"] == "Resource name"

        # Test the resource with default parameter
        resource_instance = param_resource()
        assert resource_instance.value() == "Resource: default_name"

        # Test the resource with custom parameter
        resource_instance = param_resource(name="custom_name")
        assert resource_instance.value() == "Resource: custom_name"
