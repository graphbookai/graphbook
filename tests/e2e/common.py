from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver

class GraphbookController:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        
    def run(self):
        run_button = self.driver.find_element(By.CSS_SELECTOR, "button[title='Run']")
        run_button.click()

    def get_node(self, id: str):
        return self.driver.find_element(
            By.CSS_SELECTOR, f".react-flow__node[data-id='{id}']"
        )

    def get_output_count(self, node: WebElement, nth: int = 0):
        slots = node.find_elements(
            By.CSS_SELECTOR, f".outputs .output"
        )
        if nth >= len(slots):
            raise ValueError(f"Node {node.get_attribute('data-id')} has only {len(slots)} outputs")

        slot = slots[nth]
        try:
            scroll_number = slot.find_element(
                By.CSS_SELECTOR, f"sup.ant-scroll-number"
            )
        except NoSuchElementException:
            return 0

        return int(scroll_number.get_attribute("title"))
