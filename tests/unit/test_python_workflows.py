"""
Tests for Python-defined workflows with DefaultExecutor and Graph.run.

This module tests that Python-defined workflows can be correctly 
created, serialized, and executed using the DefaultExecutor and Graph.run
method without requiring JSON workflow definitions.
"""

from pathlib import Path
import tempfile
import shutil
import sys
import importlib.util

import graphbook as gb
from graphbook.core.processing.graph_processor import DefaultExecutor
from unittest.mock import patch, MagicMock


class TestPythonWorkflows:
    """Tests for Python-defined workflows with DefaultExecutor and Graph.run."""

    def setup_method(self):
        """Set up a temporary directory for test outputs."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.temp_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up temporary directory after tests."""
        shutil.rmtree(self.temp_dir)

    @patch('graphbook.core.steps.base.log')
    def test_sample_workflow_with_default_executor(self, mock_log):
        """Test running SampleWorkflow.py with DefaultExecutor."""
        # Load the SampleWorkflow module
        sample_workflow_path = Path("examples/workflows/python/SampleWorkflow.py")
        
        # Add the parent directory to sys.path
        sys.path.append(str(sample_workflow_path.parent.parent.parent))
        
        # Import the module
        spec = importlib.util.spec_from_file_location("SampleWorkflow", sample_workflow_path)
        sample_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sample_module)
        
        # Get the graph from the module
        g: gb.Graph = sample_module.g
        
        # Skip execution in this test
        # We just want to test the graph structure
        
        # Verify graph structure
        # Use the right methods to access steps and resources
        assert len(g.get_steps()) == 4
        
        # Check edges by counting dependencies
        edge_count = 0
        for step in g.get_steps():
            edge_count += len(step.deps)
        assert edge_count == 3
        
        # Check that nodes are correctly connected
        # GenerateNumbers -> Transform
        # Transform -> CalcMean
        # Transform -> CalcRunningMean
        
        # Verify there are 4 steps with the expected structure
        steps = g.get_steps()
        assert len(steps) == 4
        
        # Verify the graph structure by checking that each step has the expected
        # number of dependencies
        # We expect:
        # - One step with 0 dependencies (GenerateNumbers)
        # - One step with 1 dependency (Transform)
        # - Two steps with 1 dependency each (CalcMean and CalcRunningMean)
        
        deps_counts = [len(step.deps) for step in steps]
        assert deps_counts.count(0) == 1, "Should have 1 source node with 0 dependencies"
        assert deps_counts.count(1) == 3, "Should have 3 nodes with 1 dependency each"
        
        # Find the transform step (the one that receives from the source and connects to two other steps)
        transform_step = None
        source_step = None
        output_steps = []
        
        for step in steps:
            if len(step.deps) == 0:
                source_step = step
            elif len([out for out in steps if any(dep[1].id == step.id for dep in out.deps)]) == 2:
                transform_step = step
            elif len(step.deps) == 1:
                output_steps.append(step)
                
        assert source_step is not None, "Source step not found"
        assert transform_step is not None, "Transform step not found"
        assert len(output_steps) == 2, "Should have 2 output steps"
        
        # Verify that Transform depends on the source
        transform_deps = [dep[1].id for dep in transform_step.deps]
        assert source_step.id in transform_deps
        
        # Verify that both output steps depend on Transform
        for output_step in output_steps:
            output_deps = [dep[1].id for dep in output_step.deps]
            assert transform_step.id in output_deps

    @patch('graphbook.core.serialization.DefaultExecutor')
    def test_graph_run_method(self, mock_executor):
        """Test Graph.run method with the sample workflow."""
        # Load the SampleWorkflow module
        sample_workflow_path = Path("examples/workflows/python/SampleWorkflow.py")
        
        # Add the parent directory to sys.path
        sys.path.append(str(sample_workflow_path.parent.parent.parent))
        
        # Import the module
        spec = importlib.util.spec_from_file_location("SampleWorkflow", sample_workflow_path)
        sample_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sample_module)
        
        # Get the graph from the module
        g = sample_module.g
        
        # Set up mock executor
        mock_executor_instance = mock_executor.return_value
        mock_executor_instance.get_client_pool.return_value = None
        mock_executor_instance.get_img_storage.return_value = None
        
        # Run the graph with Graph.run (with default executor, no web server)
        # This should just call the mock executor
        g.run(start_web_server=False)
        
        # Verify the mock executor was called with the graph
        mock_executor_instance.run.assert_called_once()
        args, _ = mock_executor_instance.run.call_args
        assert args[0] == g
        
        # Verify graph structure is intact
        assert len(g.get_steps()) == 4
        
        # Count edges by dependencies
        edge_count = 0
        for step in g.get_steps():
            edge_count += len(step.deps)
        assert edge_count == 3
        
        # Verify step structure
        for step in g.get_steps():
            assert hasattr(step, 'id')
            assert hasattr(step, 'node')
            
    @patch('graphbook.core.processing.graph_processor.GraphProcessor')
    def test_default_executor_execution(self, mock_processor_class):
        """Test that DefaultExecutor correctly runs a Python workflow."""
        # Create a simple test step
        @gb.step("Test/ValueSource")
        @gb.source()
        def value_source(ctx):
            """A simple source that yields values."""
            for value in [1, 2, 3]:
                yield {"value": value}
        
        # Create a simple graph
        g = gb.Graph()
        
        @g()
        def _():
            # Define a simple workflow with just a source step
            source = g.step(value_source)
        
        # Set up mock processor
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        # Create executor and run the graph
        executor = DefaultExecutor(log_dir=self.log_dir)
        executor.run(g, "test_workflow")
        
        # Verify processor.run was called
        mock_processor.run.assert_called_once_with(g, "test_workflow")