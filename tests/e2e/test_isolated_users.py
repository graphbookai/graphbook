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
            "--isolate_users",
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
    chrome_options.add_argument("--headless=new")  # Comment out when debugging
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

    src_count = ctl.get_output_count(ctl.get_node("8"), 0)
    assert src_count == 20000

    out_a_count = ctl.get_output_count(ctl.get_node("3"), 0)
    out_b_count = ctl.get_output_count(ctl.get_node("3"), 1)
    assert out_a_count + out_b_count == 20000


def test_isolated_experiences(server, ctl: GraphbookController):
    ctl.run()
    ctl.driver.get("http://localhost:8005")

    src_count = ctl.get_output_count(ctl.get_node("8"), 0)
    assert src_count == 0

    out_a_count = ctl.get_output_count(ctl.get_node("3"), 0)
    out_b_count = ctl.get_output_count(ctl.get_node("3"), 1)
    assert out_a_count + out_b_count == 0
