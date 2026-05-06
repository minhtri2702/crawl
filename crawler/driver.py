"""
Selenium WebDriver setup and management.
"""

import os
import logging
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from utils.helpers import retry

logger = logging.getLogger(__name__)


class WebDriverFactory:
    """Factory for creating and managing Selenium WebDriver instances."""

    def __init__(
        self,
        headless: bool = True,
        page_load_timeout: int = 60,
        implicit_wait: int = 10,
        page_load_strategy: str = "eager",
    ):
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.implicit_wait = implicit_wait
        self.page_load_strategy = page_load_strategy


    def _create_options(self) -> Options:
        """Create Chrome options for the WebDriver."""
        options = Options()

        # Set Chrome binary location explicitly
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                options.binary_location = path
                logger.debug("Using Chrome binary: %s", path)
                break

        if self.headless:
            options.add_argument("--headless=new")

        # Performance and stability options
        options.add_argument("--no-sandbox")

        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Anti-detection options
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Use eager page load strategy (don't wait for all resources)
        options.page_load_strategy = self.page_load_strategy

        # Preferences
        prefs = {

            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.media_stream": 2,
        }
        options.add_experimental_option("prefs", prefs)

        return options

    @retry(max_attempts=3, delay=5, backoff=2.0, exceptions=(WebDriverException,))
    def create_driver(self) -> WebDriver:
        """
        Create and return a configured Chrome WebDriver.

        Returns:
            Configured WebDriver instance.
        """
        options = self._create_options()

        # Use webdriver-manager to handle ChromeDriver binary
        service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)

        # Set timeouts
        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(self.implicit_wait)

        # Execute script to mask automation
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['vi-VN', 'vi', 'en-US', 'en']
                });
            """
            },
        )

        logger.info("Chrome WebDriver created successfully")
        return driver

    @staticmethod
    def destroy_driver(driver: Optional[WebDriver]) -> None:
        """Safely quit a WebDriver instance."""
        if driver is not None:
            try:
                driver.quit()
                logger.info("WebDriver quit successfully")
            except WebDriverException as e:
                logger.warning("Error quitting WebDriver: %s", e)
