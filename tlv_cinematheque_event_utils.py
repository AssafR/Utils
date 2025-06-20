import re
from dataclasses import dataclass
from typing import Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from time import sleep

@dataclass
class CinemathequeEvent:
    header: str
    text_description: str
    full_description: str
    dates: Dict[str, List[str]]
    url: str = None

    # formatted_start_time: str
    # formatted_end_time: str

    def __str__(self):
        return (f"Event({self.header}, {self.text_description}, {self.full_description}, "
                f"{self.dates}"
                # f", {self.formatted_start_time}, {self.formatted_end_time})"
                )

    def __repr__(self):
        return (f"Event({self.header}, {self.text_description}, {self.full_description}, "
                f"{self.dates}, "
                # f"{self.formatted_start_time}, {self.formatted_end_time})"
                )

    # def event_to_url(self):
    #     return create_calendar_event_url(self.header, self.full_description,
    #                                      self.formatted_start_time, self.formatted_end_time)
    #


def split_on_double_newlines(st):
    # Split the string on two or more consecutive newlines
    return re.split(r'\n{2,}', st)


def extract_date(input_string):
    # Define a regular expression pattern for matching the date
    date_pattern = re.compile(r'(\d{1,2}-\d{1,2}-\d{4})')

    # Search for the date pattern in the input string
    match = re.search(date_pattern, input_string)

    # Check if a match is found
    if match:
        # Extract the matched date
        extracted_date = match.group(1)
        return extracted_date
    else:
        return None


def extract_time(input_string):
    # Define a regular expression pattern for matching time
    time_pattern = re.compile(r'\b(\d{1,2}:\d{2})\b')

    # Search for the time pattern in the input string
    match = re.search(time_pattern, input_string)

    # Check if a match is found
    if match:
        # Extract the matched time
        extracted_time = match.group(1)
        return extracted_time
    else:
        return None

def extract_dates_using_submit_form(url):
    # Start Chrome browser
    driver = webdriver.Chrome()

    # Point the browser to the URL
    driver.get(url)

    try:
        # Wait for the date dropdown to be present
        date_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'smdate_b'))
        )

        dates = {}

        # Select a date option (change the index as needed)
        date_select = Select(date_dropdown)
        for date_selection_number, date_selection in enumerate(date_select.options):
            extracted_date = extract_date(date_selection.text)
            if extracted_date is None:
                continue
            date_select.select_by_index(date_selection_number)  # Change the index based on the desired option

            # Wait for the time dropdown to be present
            time_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'smtime_b'))
            )
            sleep(1)

            # Select a time option (change the index as needed)
            time_select = Select(time_dropdown)
            # Extract the time options for the selected date
            extracted_times = [extract_time(time_selection.text) for time_selection in time_select.options]
            dates[extracted_date] = [d for d in extracted_times if d is not None]

        #
        # # # Submit the form
        # # submit_button = driver.find_element(By.ID, 'sgotoorder')
        # # submit_button.click()
        #
        # # Wait for the page to load after submission
        # WebDriverWait(driver, 10).until(
        #     # EC.presence_of_element_located((By.ID, 'submit reminder-btn'))
        #     EC.visibility_of_element_located((By.ID, 'smtime_b'))
        # )

        # Get the HTML content after form submission
        page_html = driver.page_source[:]
        # updated_dom = driver.execute_script("return document.documentElement.outerHTML;")[:]
        # print(page_html)

    finally:
        # Close the browser window
        driver.quit()
    return page_html, dates

def extract_static_content_old(html_content):
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    # Extract header, description, and time
    event_data = {}
    h3_element = soup.find('div', class_='title').find('h3')
    event_data['header'] = h3_element.get_text(strip=True)
    h5_element = soup.find('div', class_='text-wraper').find('h5')
    if h5_element is None: # Special bug fix
        h5_element = h3_element.parent.parent
    event_data['text_description'] = h5_element.get_text(strip=True)
    event_data['full_description'] = soup.find('div', class_='text-wraper').get_text(strip=False)
    fd = soup.find('div', class_='text-wraper')
    event_data['header'] = fd.contents[3]
    event_data['description'] = fd.contents[5]
    return event_data

def extract_static_content_from_html_to_event(html_content: str, dates, url: str) -> CinemathequeEvent:
    # Parse HTML content
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Extract header, description, and time
        h3_element = soup.find('div', class_='title').find('h3')
        header = h3_element.get_text(strip=True) # Obsolete ?
        h5_element = soup.find('div', class_='text-wraper').find('h5')
        if h5_element is None:  # Special bug fix
            h5_element = h3_element.parent.parent
        text_description = h5_element.get_text(strip=True)
        full_description = soup.find('div', class_='text-wraper').get_text(strip=False)
        fd = soup.find('div', class_='text-wraper')
        header = fd.contents[3]
        # description = fd.contents[5]
        dates = dates

        event_data = CinemathequeEvent(header, text_description, full_description, dates, url)
        return event_data
    except Exception as e:
        print(f"An error occurred: {e}")
        raise e


def extract_visible_text(url):
    try:
        # Set up Chrome options to run headlessly
        chrome_options = Options()
        chrome_options.add_argument("--headless")

        # Create a Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)

        # Navigate to the URL
        driver.get(url)

        # Wait for some time (you can adjust this based on the page loading time)
        driver.implicitly_wait(5)

        # Get the page source
        page_source = driver.page_source

        # Close the browser
        driver.quit()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

        # Extract visible text
        visible_text = soup.get_text()

        # Print the extracted text
        print(visible_text)

    except Exception as e:
        print(f"An error occurred: {e}")


