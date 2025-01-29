import requests
import yagmail
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Suppress TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

websites = [
    {"url": "https://vergabeportal-bw.de/Satellite/common/project/search.do?method=searchExtended", 
     "keywords": ["catering", "verpflegung", "lebensmittel", "kantin", "speise", "hotel", "essen"]},
]

# Email configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHES_FILE = os.path.join(SCRIPT_DIR, "matches.json")
TEXT_PARTS_FILE = "extracted_text_parts.json"

class Match:
    def __init__(self, title, link):
        self.title = title
        self.link = link

    def to_dict(self):
        return {"title": self.title, "link": self.link}

def clear_matches_file():
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)
        print(f"{MATCHES_FILE} has been cleared.")
    else:
        print(f"{MATCHES_FILE} does not exist. Creating a new empty file.")
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)

def load_previous_matches():
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "r") as file:
            return json.load(file)
    return {}

def save_matches(matches):
    with open(MATCHES_FILE, "w") as file:
        json.dump(matches, file, indent=4)

def save_text_parts(text_parts):
    with open(TEXT_PARTS_FILE, "w") as file:
        json.dump(text_parts, file, indent=4)

def extract_titles_and_links_with_selenium(url):
    extracted_data = []
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Handle cookies popup if necessary
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'alle akzeptieren')]"))
            ).click()
            print("Cookies popup dismissed.")
        except Exception:
            print("No cookies popup found.")

        # Wait for elements to load
        title_elements = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "word-break"))
        )

        link_elements = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "noTextDecorationLink"))
        )

        print(f"Found {len(link_elements)} links.")

        for title_element, link_element in zip(title_elements, link_elements):
            try:
                title = title_element.text.strip()
                link = "https://vergabeportal-bw.de" + link_element.get_attribute("href")[29:-19]
                extracted_data.append(Match(title, link).to_dict())
                print(f"Extracted: {title}, {link}")
            except Exception as e:
                print(f"Error extracting data: {e}")

    except Exception as e:
        print(f"Error loading the page: {e}")
    finally:
        driver.quit()

    return extracted_data

def check_keywords(text, keywords):
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

def send_email(new_matches):
    subject = "Neue Ausschreibungen verfügbar!!"
    body = "Die folgenden neuen Übereinstimmungen wurden gefunden:\n\n"

    for match in new_matches:
        title = match.get("title", "No Title")
        link = match.get("link", "No Link")
        body += f"Title: {title}\nLink: {link}\n\n"

    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_PASSWORD)
        yag.send("Henrik.Hemmer@flc-group.de", subject, body)
        print("Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    clear_matches_file()
    previous_matches = load_previous_matches()
    print("Previous Matches:", previous_matches)
    new_matches = []

    for site in websites:
        url = site["url"]
        keywords = site["keywords"]

        # Extract all titles and links
        extracted_data = extract_titles_and_links_with_selenium(url)
        save_text_parts(extracted_data)

        # Determine new matches
        if url not in previous_matches:
            previous_matches[url] = []

        for data in extracted_data:
            title = data.get("title", "")

            if check_keywords(title, keywords) and data not in previous_matches[url]:
                new_matches.append(data)
                previous_matches[url].append(data)

    # Send an email if there are new matches
    if new_matches:
        send_email(new_matches)

    # Save the updated matches to the file
    save_matches(previous_matches)

if __name__ == "__main__":
    main()
