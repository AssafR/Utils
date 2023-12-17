import re
from time import sleep

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from urllib.parse import quote
import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


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

def extract_with_submit_form(url):
    # Start Chrome browser
    driver = webdriver.Chrome()

    # Replace 'your_url' with the actual URL of the page
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
            dates[extracted_date] = [extract_time(time_selection.text) for time_selection in time_select.options]
            dates[extracted_date] = [d for d in dates[extracted_date] if d!=None]


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


def extract_invitation_from_html(html_content, dates):
    event_data = {}

    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract header, description, and time
    event_data['header'] = soup.find('div', class_='title').find('h3').get_text(strip=True)
    event_data['text_description'] = soup.find('div', class_='text-wraper').find('h5').get_text(strip=True)
    event_data['full_description'] = soup.find('div', class_='text-wraper').get_text(strip=False)

    fd = soup.find('div', class_='text-wraper')
    event_data['header'] = fd.contents[3]
    event_data['description'] = fd.contents[5]

    # time_str = soup.find('div', class_='screenings-model').find('option')['value'].split('~')[0]
    # # Parse date and time using dateutil.parser
    # event_datetime = parser.parse(time_str)

##
    # date_str = \
    # soup.find('div', class_='screenings-model').find('select', id='smdate_b').find('option')['value'].split('~')[0]
    # time_option = soup.find('div', class_='screenings-model').find('select', id='smtime_b').find('option',
    #                                                                                              {'data-time': True})
    # time_str = time_option['data-time'] if time_option else None
    event_datetimes = []
    for date_str in dates:
        for time_str in dates[date_str]:
            event_datetime = parser.parse(f"{date_str} {time_str}") if date_str and time_str else None
            if event_datetime:
                event_datetimes.append(event_datetime)

    for event_datetime in event_datetimes:
        event_datetime_end = event_datetime + datetime.timedelta(minutes=180) if event_datetime else None
        # Format the date and time for the Google Calendar URL
        event_data['formatted_start_time'] = event_datetime.strftime('%Y%m%dT%H%M%S')
        event_data['formatted_end_time'] = event_datetime_end.strftime('%Y%m%dT%H%M%S')

    return event_data

    # formatted_header = quote(header)
    # formatted_description = quote(full_description)
    #
    # # Create Google Calendar Event URL
    # google_calendar_url = f'https://calendar.google.com/calendar/u/0/r/eventedit?text={formatted_header}&dates={formatted_datetime}/{formatted_datetime_end}&details={formatted_description}'
    #
    # print("Header:", header)
    # print("Description:", description)
    # print("Time:", event_datetime)
    # print("Google Calendar Event URL:", google_calendar_url)


def extract_text_after_js(url):
    try:
        # Set up Chrome options to run headlessly
        chrome_options = Options()
        chrome_options.add_argument("--headless")

        # Create a Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)

        # Navigate to the URL
        driver.get(url)

        # Set a maximum waiting time for dynamic content (adjust as needed)
        wait = WebDriverWait(driver, 10)

        # Wait for an element to be present, assuming the content is dynamically loaded
        # element = wait.until(EC.presence_of_element_located((By.XPATH, "input-wraper")))
        element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "input-wraper")))
        # Print the content of the web page after JavaScript is executed
        # print(driver.page_source)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract visible text
        visible_text = soup.get_text()
        print(visible_text)

        # Close the browser
        driver.quit()

    except Exception as e:
        print(f"An error occurred: {e}")


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


def read_web_page_headless(url):
    try:
        # Set up Chrome options to run headlessly
        chrome_options = Options()
        chrome_options.add_argument("--headless")

        # Create a Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)

        # Navigate to the URL
        driver.get(url)

        # Wait for some time (you can adjust this based on the page loading time)
        driver.implicitly_wait(10)

        # Print the content of the web page
        # print(driver.page_source)

        # Close the browser
        result = driver.page_source[:]
        driver.quit()

        return result

    except Exception as e:
        print(f"An error occurred: {e}")


def read_web_page(url):
    try:
        # Send a GET request to the URL
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Print the content of the web page
            print(response.text)
        else:
            print(f"Error: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")


# Example usage
url = "https://www.cinema.co.il/event/%d7%94%d7%90%d7%a8%d7%93-%d7%91%d7%95%d7%99%d7%9c%d7%93-%d7%94%d7%91%d7%a8%d7%99%d7%97%d7%94/"
# url = "https://www.cinema.co.il/event/%d7%9c%d7%a8%d7%93%d7%95%d7%a3-%d7%90%d7%97%d7%a8%d7%99-%d7%a6%d7%99%d7%99%d7%a1%d7%99%d7%a0%d7%92-%d7%90%d7%99%d7%99%d7%9e%d7%99-%d7%a4%d7%a1%d7%98%d7%99%d7%91%d7%9c-%d7%92%d7%90%d7%94/"
# read_web_page(url)
# read_web_page_headless(url)
# extract_visible_text(url)
# extract_text_after_js(url)
# html_content = read_web_page_headless(url)
html_content, dates = extract_with_submit_form(url)
event = extract_invitation_from_html(html_content, dates)
print(event)

