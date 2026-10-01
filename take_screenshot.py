#!/usr/bin/env python3
"""
take_screenshot.py

A tiny helper script that opens a URL in headless Chrome
and writes a full‑page screenshot to disk.

Requirements:
  * Python 3.8+
  * selenium 4.x
  * webdriver‑manager 4.x (automatically installs ChromeDriver)
  * Chrome or Chromium (any recent version)

Install the dependencies with:

    pip install selenium webdriver-manager

Usage:

    python take_screenshot.py https://example.com screenshot.png

If you omit the output file name, it defaults to 'screenshot.png'.
"""

import sys
import argparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def take_screenshot(url: str, out_path: Path, wait: int = 3):
    """
    Open the URL in headless Chrome and capture a full‑page screenshot.

    :param url: Target URL to visit
    :param out_path: Path where the PNG will be written
    :param wait: Seconds to wait after page load (default 3)
    """
    # Headless Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")          # Not needed on Windows
    chrome_options.add_argument("--no-sandbox")          # For Linux containers
    chrome_options.add_argument("--window-size=1920,1080")  # Set a reasonable viewport

    # Initialise WebDriver with webdriver‑manager
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to the page
        driver.get(url)

        # Optional: wait for the page to fully render
        driver.implicitly_wait(wait)

        # For a full‑page screenshot, we need the page height
        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1920, page_height)

        # Take screenshot
        driver.save_screenshot(str(out_path))
        print(f"Screenshot saved to {out_path}")

    finally:
        driver.quit()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Open a URL in headless Chrome and take a screenshot."
    )
    parser.add_argument("url", help="The URL to capture")
    parser.add_argument(
        "-o",
        "--output",
        default="screenshot.png",
        help="Output PNG file (default: screenshot.png)",
    )
    parser.add_argument(
        "-w",
        "--wait",
        type=int,
        default=3,
        help="Seconds to wait after page load (default: 3)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    take_screenshot(args.url, Path(args.output), wait=args.wait)


if __name__ == "__main__":
    main()
