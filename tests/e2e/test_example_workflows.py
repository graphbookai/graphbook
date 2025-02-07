import subprocess
import time
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from .common import GraphbookController


@pytest.fixture(scope="module")
def server():
    # Start the graphbook server
    server_process = subprocess.Popen(
        [
            "python",
            "-m",
            "graphbook.main",
            "--web_dir",
            "web/dist",
            "--root_dir",
            "examples/workflows/class-based/simple_workflow",
        ]
    )
    time.sleep(5)  # Wait for the server to start
    yield
    # Stop the server
    server_process.terminate()
    server_process.wait()


@pytest.fixture(scope="module")
def ctl():
    # Set up the web driver
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Comment out when debugging
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(
        options=chrome_options, service=ChromeService(ChromeDriverManager().install())
    )
    driver.implicitly_wait(10)
    driver.get("http://localhost:8005")  # Navigate to the server address
    yield GraphbookController(driver)
    # Close the web driver
    driver.quit()


def test_run_example_workflow(server, ctl: GraphbookController):
    ctl.run()
    time.sleep(5)

    src_count = ctl.get_output_count(ctl.get_node("1"), 0)
    assert src_count == 10

    out_a_count = ctl.get_output_count(ctl.get_node("0"), 0)
    out_b_count = ctl.get_output_count(ctl.get_node("0"), 1)
    assert out_a_count + out_b_count == 10
