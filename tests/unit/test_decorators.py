from graphbook.core.decorators import (
    step,
    param,
    source,
    output,
    resource,
    event,
    get_steps,
    get_resources,
    StepClassFactory,
    ResourceClassFactory,
)
from graphbook.core import steps


class TestStepDecorators:
    """Test the step decorator functionality."""

    def setup_method(self):
        """Reset the global state before each test."""
        # Call get_steps and get_resources to clear the global state
        get_steps()
        get_resources()

    def test_basic_step_decorator(self):
        """Test that a basic step can be created with the step decorator."""

        @step("Test/BasicStep")
        def basic_step(ctx, data):
            data["processed"] = True
            return data

        steps_dict = get_steps()
        assert "BasicStep" in steps_dict
        assert steps_dict["BasicStep"].Category == "Test"

        # Test the step functionality
        step_instance = steps_dict["BasicStep"]()
        test_data = {}
        result = step_instance(test_data)
        assert "out" in result
        assert result["out"][0]["processed"] is True

    def test_step_with_parameters(self):
        """Test that parameters can be added to steps."""

        @step("Test/ParamStep")
        @param("value", "number", default=42, description="Test value")
        def param_step(ctx, data):
            print(dir(ctx))
            data["value"] = ctx.value
            return data

        steps_dict = get_steps()
        assert "ParamStep" in steps_dict
        step_class = steps_dict["ParamStep"]

        # Check parameter metadata
        assert "value" in step_class.Parameters
        assert step_class.Parameters["value"]["default"] == 42
        assert step_class.Parameters["value"]["description"] == "Test value"

        # Test the step with default parameter
        step_instance = step_class()
        test_data = {}
        result = step_instance(test_data)
        assert result["out"][0]["value"] == 42

        # Test the step with custom parameter
        step_instance = step_class(value=100)
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

        steps_dict = get_steps()
        assert "SourceStep" in steps_dict
        step_class = steps_dict["SourceStep"]

        # Check that it's a source step
        assert issubclass(step_class, steps.GeneratorSourceStep)

        # Test the source step functionality
        step_instance = step_class()
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

        steps_dict = get_steps()
        assert "OutputStep" in steps_dict
        step_class = steps_dict["OutputStep"]

        # Check output slots
        assert step_class.Outputs == ["success", "failure"]

        # Test routing to success
        step_instance = step_class()
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

        steps_dict = get_steps()
        assert "EventStep" in steps_dict
        step_class = steps_dict["EventStep"]

        # Test events
        step_instance = step_class()
        assert step_instance.initialized is True

        test_data = {}
        result = step_instance(test_data)
        assert result["out"][0]["initialized"] is True

        step_instance.on_clear()
        assert step_instance.initialized is False


class TestResourceDecorators:
    """Test the resource decorator functionality."""

    def setup_method(self):
        """Reset the global state before each test."""
        get_steps()
        get_resources()

    def test_basic_resource_decorator(self):
        """Test that a basic resource can be created with the resource decorator."""

        @resource("Test/SimpleResource")
        def simple_resource(ctx):
            return "resource_value"

        resources_dict = get_resources()
        assert "SimpleResource" in resources_dict
        assert resources_dict["SimpleResource"].Category == "Test"

        # Test the resource value
        resource_instance = resources_dict["SimpleResource"]()
        assert resource_instance.value() == "resource_value"

    def test_resource_with_parameters(self):
        """Test that parameters can be added to resources."""

        @resource("Test/ParamResource")
        @param("name", "string", default="default_name", description="Resource name")
        def param_resource(ctx):
            return f"Resource: {ctx.name}"

        resources_dict = get_resources()
        assert "ParamResource" in resources_dict
        resource_class = resources_dict["ParamResource"]

        # Check parameter metadata
        assert "name" in resource_class.Parameters
        assert resource_class.Parameters["name"]["default"] == "default_name"
        assert resource_class.Parameters["name"]["description"] == "Resource name"

        # Test the resource with default parameter
        resource_instance = resource_class()
        assert resource_instance.value() == "Resource: default_name"

        # Test the resource with custom parameter
        resource_instance = resource_class(name="custom_name")
        assert resource_instance.value() == "Resource: custom_name"


class TestClassFactories:
    """Test the NodeClassFactory classes directly."""

    def test_step_class_factory(self):
        """Test the StepClassFactory directly."""
        factory = StepClassFactory("TestStep", "Test")
        factory.param("value", "number", default=10)
        factory.event("on_data", lambda ctx, data: data.update({"processed": True}))
        factory.doc("Test step docstring")

        step_class = factory.build()

        # Check class properties
        assert step_class.__name__ == "TestStep"
        assert step_class.Category == "Test"
        assert step_class.__doc__ == "Test step docstring"
        assert "value" in step_class.Parameters

        # Test instance
        step_instance = step_class(value=20)
        assert step_instance.value == 20

        test_data = {}
        step_instance.on_data(test_data)
        assert test_data["processed"] is True

    def test_resource_class_factory(self):
        """Test the ResourceClassFactory directly."""
        factory = ResourceClassFactory("TestResource", "Test")
        factory.param("config", "string", default="default_config")
        factory.event("value", lambda ctx: f"Resource with config: {ctx.config}")
        factory.doc("Test resource docstring")

        resource_class = factory.build()

        # Check class properties
        assert resource_class.__name__ == "TestResource"
        assert resource_class.Category == "Test"
        assert resource_class.__doc__ == "Test resource docstring"
        assert "config" in resource_class.Parameters

        # Test instance
        resource_instance = resource_class(config="custom_config")
        assert resource_instance.config == "custom_config"
        assert resource_instance.value() == "Resource with config: custom_config"
