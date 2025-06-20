import contextlib
from urllib.request import urlopen

import requests
from dateutil import parser
import urllib.parse
# from urllib.parse import quote
import datetime
from zoneinfo import ZoneInfo  # Python 3.9


from tlv_cinematheque_event_utils import *
from tlv_cinematheque_event_utils import CinemathequeEvent


def extract_invitation_from_html(html_content, dates, url=None) -> CinemathequeEvent:
    event_data: CinemathequeEvent = extract_static_content_from_html_to_event(html_content, dates, url)

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

    # for event_datetime in event_datetimes:
    #     event_datetime_end = event_datetime + datetime.timedelta(minutes=180) if event_datetime else None
    #     # Format the date and time for the Google Calendar URL
    #     event_data['formatted_start_time'] = event_datetime.strftime('%Y%m%dT%H%M%S')
    #     event_data['formatted_end_time'] = event_datetime_end.strftime('%Y%m%dT%H%M%S')

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
        return visible_text

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


def read_web_page(page_url):
    try:
        # Send a GET request to the URL
        response = requests.get(page_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Print the content of the web page
            return response.text
        else:
            return f"Error: {response.status_code}"

    except Exception as e:
        print(f"An error occurred: {e}")


def make_tiny(url):
    tiny_request_url = ('http://tinyurl.com/api-create.php?' + urllib.parse.urlencode({'url': url}))
    with contextlib.closing(urlopen(tiny_request_url)) as response:
        return response.read().decode('utf-8 ')


def create_calendar_event_url(header, description, start_date, start_datetime, end_date=None, end_time=None):
    # Combine date and time into a datetime object
    # event_datetime = datetime.datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
    event_datetime = extract_datetime_from_date_and_time(start_date, start_datetime)
    start_datetime = event_datetime.isoformat()  # event_datetime.isoformat()
    if end_time is None or end_date is None:
        end_datetime = (event_datetime + datetime.timedelta(hours=3)).isoformat()
    else:
        end_datetime = extract_datetime_from_date_and_time(end_date, end_time).isoformat()

    # Encode the event details to be URL-safe
    h_encoded = urllib.parse.quote(header)
    desc_encoded = urllib.parse.quote(description)
    # Create the URL
    # base_url = 'https://calendar.google.com/calendar/r/eventedit'
    # base_url = 'https://calendar.google.com/calendar/u/0/r/eventedit?'
    base_url = 'https://www.google.com/calendar/render?action=TEMPLATE&'
    start_time_fmt = start_datetime.replace('-', '').replace(':', '')
    end_time_fmt = end_datetime.replace('-', '').replace(':', '')

    location = 'Tel Aviv Cinematheque'
    location = urllib.parse.quote(location)
    add_addresses = ['yshevach@yahoo.com']
    add_addresses_params = '&add=' + ','.join(add_addresses) if add_addresses else ''

    url = f"{base_url}text={h_encoded}&dates={start_time_fmt}Z/{end_time_fmt}Z&location={location}&details={desc_encoded}{add_addresses_params}"

    return url


def extract_datetime_from_date_and_time(start_date, start_datetime):
    event_datetime = datetime.datetime.strptime(f"{start_date} {start_datetime}", "%d-%m-%Y %H:%M")
    event_datetime.replace(tzinfo=ZoneInfo('Asia/Jerusalem'))  # Input is in Israel time
    event_datetime = event_datetime.astimezone(datetime.timezone.utc)
    return event_datetime


def create_calendar_urls_for_event(event_url):
    html_content, dates = extract_dates_using_submit_form(event_url)
    event = extract_invitation_from_html(html_content, dates, event_url)
    lines = [t for t in split_on_double_newlines(event.full_description) if t]
    event_description = lines[0].splitlines()[0]

    # Insert new element at index 0 and push others onto the next index
    event.full_description = event.full_description[0:1200] # Otherwise URL is too long
    full_description_with_url = f'<A HREF="{event_url}">להזמנת כרטיס</A><br/>{event.full_description}'
    urls = []
    for date, times in dates.items():
        for time in times:
            url: str = create_calendar_event_url(event_description, full_description_with_url, date, time, event_url)
            urls.append(url)
    print("Description:", event_description)
    print("Dates:", dates)
    # print("Full Description (HTML):", event.full_description)
    return urls


# noinspection PyShadowingNames
def extract_events_urls_from_series_page(event_url):
    series_html = read_web_page_headless(event_url)
    series_soup = BeautifulSoup(series_html, 'html.parser')
    series_events = series_soup.find_all('a', string="לפרטים נוספים", href=True)
    hrefs = set(event['href'] for event in series_events)
    cal_urls = []
    for url_no, event_url in enumerate(hrefs):
        print(f"Event: {url_no}, url:{event_url}")
        urls = create_calendar_urls_for_event(event_url)
        cal_urls.extend(urls)
        # if url_no > 2:
        #     break
    return cal_urls


# Example usage
# url = "https://www.cinema.co.il/event/%d7%94%d7%90%d7%a8%d7%93-%d7%91%d7%95%d7%99%d7%9c%d7%93-%d7%94%d7%91%d7%a8%d7%99%d7%97%d7%94/"
# url = "https://www.cinema.co.il/event/%d7%9c%d7%a8%d7%93%d7%95%d7%a3-%d7%90%d7%97%d7%a8%d7%99-%d7%a6%d7%99%d7%99%d7%a1%d7%99%d7%a0%d7%92-%d7%90%d7%99%d7%99%d7%9e%d7%99-%d7%a4%d7%a1%d7%98%d7%99%d7%91%d7%9c-%d7%92%d7%90%d7%94/"
# url = "https://www.cinema.co.il/event/%d7%97%d7%aa%d7%95%d7%a0%d7%94-%d7%a4%d7%a8%d7%a1%d7%99%d7%aa-%d7%a4%d7%a1%d7%98%d7%99%d7%91%d7%9c-%d7%92%d7%90%d7%94/"
event_url_1 = 'https://www.cinema.co.il/event/%d7%91%d7%a2%d7%91%d7%95%d7%a8-%d7%97%d7%95%d7%a4%d7%9f-%d7%93%d7%95%d7%9c%d7%a8%d7%99%d7%9d/'
series_url_1 = 'https://www.cinema.co.il/%d7%9e%d7%99%d7%95%d7%92%d7%99%d7%9e%d7%91%d7%95-%d7%95%d7%a2%d7%93-%d7%a4%d7%a8%d7%a9/'
series_url_2 = 'https://www.cinema.co.il/%d7%9e%d7%99%d7%95%d7%92%d7%99%d7%9e%d7%91%d7%95-%d7%95%d7%a2%d7%93-%d7%a4%d7%a8%d7%a9/'
event_url_2 = 'https://www.cinema.co.il/event/%d7%90%d7%99%d7%a9-%d7%94%d7%a7%d7%a9-%d7%a1%d7%a8%d7%98%d7%94%d7%95%d7%a4%d7%a2%d7%94-%d7%a1%d7%90%d7%95%d7%a0%d7%93%d7%98%d7%a8%d7%90%d7%a7-2024/'

# calendar_urls = extract_events_urls_from_series_page(event_url_2)
calendar_urls = create_calendar_urls_for_event(event_url_2)

for calendar_url in calendar_urls:
    print("Click this long link to create the event:\n", calendar_url)

print('---')
for calendar_url in calendar_urls:
    print("Click this short link to create the event:\n", make_tiny(calendar_url))
print('---')
