import subprocess
import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.options import Options


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
def driver():
    # Set up the web driver
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Comment out when debugging
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(
        options=chrome_options, service=ChromeService(ChromeDriverManager().install())
    )
    driver.implicitly_wait(10)
    yield driver
    # Close the web driver
    driver.quit()


def test_run_example_workflow(server, driver):
    driver.get("http://localhost:8005")  # Navigate to the server address

    def run():
        run_button = driver.find_element(By.CSS_SELECTOR, "button[title='Run']")
        run_button.click()

    def get_node(id: str):
        return driver.find_element(
            By.CSS_SELECTOR, f".react-flow__node[data-id='{id}']"
        )

    def get_output_count(node: WebElement, nth: int = 0):
        els = node.find_elements(
            By.CSS_SELECTOR, f".outputs .output sup.ant-scroll-number"
        )
        assert nth < len(els)
        return int(els[nth].get_attribute("title"))

    run()
    time.sleep(5)

    src_count = get_output_count(get_node("1"), 0)
    assert src_count == 10

    out_a_count = get_output_count(get_node("0"), 0)
    out_b_count = get_output_count(get_node("0"), 1)
    assert out_a_count + out_b_count == 10
