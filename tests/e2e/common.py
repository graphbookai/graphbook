from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver


class GraphbookController:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def run(self, block: bool = True, timeout: int = 60):
        """
        Runs the workflow that is present in the Graphbook UI.

        Args:
            block (bool): Whether to block until the run is finished.
            timeout (int): The maximum time to wait for the run to finish.
        """
        run_selector = "button[title='Run']"
        pause_selector = "button[title='Pause']"
        # Start run
        run_button = self.driver.find_element(By.CSS_SELECTOR, run_selector)
        run_button.click()
        if block:
            # Wait for run to start
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, pause_selector))
                )
            except TimeoutException:
                # Run could have been too fast. Check for outputs
                if not self.driver.find_elements(
                    By.CSS_SELECTOR, ".outputs .output sup.ant-scroll-number"
                ):
                    raise Exception(
                        "Run did not start, or this workflow isn't giving any outputs"
                    )
            # Wait for run to finish
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, run_selector))
            )

    def get_node(self, id: str):
        return self.driver.find_element(
            By.CSS_SELECTOR, f".react-flow__node[data-id='{id}']"
        )

    def get_output_count(self, node: WebElement, nth: int = 0):
        slots = node.find_elements(By.CSS_SELECTOR, f".outputs .output")
        if nth >= len(slots):
            raise ValueError(
                f"Node {node.get_attribute('data-id')} has only {len(slots)} outputs"
            )

        slot = slots[nth]
        try:
            scroll_number = slot.find_element(By.CSS_SELECTOR, f"sup.ant-scroll-number")
        except NoSuchElementException:
            return 0

        return int(scroll_number.get_attribute("title"))
