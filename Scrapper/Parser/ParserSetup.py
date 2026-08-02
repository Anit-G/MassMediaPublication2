import random
import time
import requests
import Utils.Config_vars as config
import Utils.Central_Logger as log

from Utils.DB_Operations import DBOps
from .ParseToc import ParseToc
from .ParseChapters import ParseChapters
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from time import sleep

class ParserSetup:
    def __init__(self) -> None:
        self.USER_AGENTS = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
        ]
        
    def _setup_driver(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        user_agent = random.choice(self.USER_AGENTS)
        options.add_argument(f'user-agent={user_agent}')
        options.add_argument('--headless')
        options.add_argument("--log-level=3")  # Suppress most logs
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')  # Bypass detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install(),log_output="Defunk/web.log"), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")  # Bypass webdriver detection
        return driver
    
    def _get_responce(self, url: str, id: str ) -> str | None:
        start = time.time()
        response = requests.get(url, headers={"User-Agent": random.choice(self.USER_AGENTS)})
        end = time.time()
        log.INFO(f"[{id}] Status code for request: {response.status_code}, Time: {"{:.2f}".format(end-start)}")
        if(response.status_code not in range(200,229)):
            log.ERROR(f"[{id}] Error in request, responce code: {response.status_code}")
            with DBOps() as db:
                db.update_failure_count(int(id))
            return None
        return response.text
    
    def _scrap_metadata(self, soup, book_data) -> dict:
        """

        Args:
            soup (BeautifulSoup): beautiful soup object used for parsing the static HTML page
            book_data (Dict): dict['source']

        Returns:
            dict: dict{
                "language" : string,
                "source" : string,
                "subject" : string,
                "book_title": string,
                "summary" : string,
                "content_url" : string (url where the book content will be scraped from),
                "ebook_no" : string
            }
        """
         # Get "Read Online" link, from the source link
        book_number = book_data['source'].split('/')[-1]
        
        if book_number:
            log.INFO(f"META: [{book_number}] Defining content url and ebook_no")
            book_data['content_url'] = "https://www.gutenberg.org/cache/epub/"+book_number+"/pg"+book_number+"-images.html"
            book_data['ebook_no'] = book_number
        else:
            # raise error that content url was not found
            log.ERROR("No book number found in the URL - severe")
            book_data['content_url'] = "NONE"
            book_data['ebook_no'] = "NONE"
        
        # Get Language
        log.INFO(f"META: [{book_number}] Scrapping language type")
        language_row = soup.find('tr', {'property': 'dcterms:language'})
        lang_c = language_row.find('td')
        if lang_c:            
            lang_c = lang_c.text.strip()
            book_data['language'] = lang_c.split('\n')[-1] # I only the language not the entire row

        # If the book is not in english ignore it, remove from DB
        if "english" not in lang_c.lower():
            log.DEBUG(f"[{book_number}] Language is not english - lead flow to deadend")
            with DBOps() as db:
                db.update_status_meta(book_number, "REMOVE")
            return {}
        
        # Get subject
        log.INFO(f"META: [{book_number}] Scraping subject type")
        subject_row = soup.find_all('td', {'property': 'dcterms:subject'})
        subject = ", ".join([s.get_text(strip=True) for s in subject_row])
        
        # If the book is a drama or poet ignore it - remove from DB
        if "poet" in subject.lower() or "drama" in subject.lower():
            log.DEBUG(f"[{book_number}] subject contains drama - lead flow to deadend")
            with DBOps() as db:
                db.update_status_meta(book_number, "REMOVE")
        
        if subject:
            book_data['subject'] = subject
        
        # Get book title
        log.INFO(f"META: [{book_number}] Scraping book title")
        title = soup.find('h1')
        book_data['book_title'] = title.text.strip() if title else "Unknown Title"

        # Get summary
        log.INFO(f"META: [{book_number}] Scraping book summary")
        summary_row = soup.find('th', string='Summary')
        if summary_row:
            summary = summary_row.find_next('td').text.strip()
            book_data['summary'] = summary
        else:
            log.DEBUG(f"META: [{book_number}] No summary found")
            book_data['summary'] = ""
        return book_data
    
    def get_metadata(self, url: str) -> dict | None:
        """
        Args:
            url (string): source URL where the metadata for the book needs to be scraped from

        Returns:
            dict: dict: dict{
                "language" : string,
                "source" : string,
                "subject" : string,
                "book_title": string,
                "summary" : string,
                "content_url" : string (url where the book content will be scraped from),
                "ebook_no" : string
            }
        """
        # run up the  driver
        if config.USE_REQUEST:
            log.INFO(f"META: Getting HTML static page via standard requests")
            ps = self._get_responce(url, url.split('/')[-1])
        else:
            log.INFO(f"META: Getting HTML static page via Selenium Webdriver")
            driver = self._setup_driver()
            driver.get(url)
            sleep(3)
            ps = driver.page_source
            
        start = time.time()
        if ps and len(ps) > 256:
            soup = BeautifulSoup(ps, 'html.parser') 
        else:
            log.DEBUG(f"META: Page is unparsable, lenght < 256")
            return None
        
        # Get metadata for the book
        book_data = {}
        book_data['source'] = url
        book_data = self._scrap_metadata(soup, book_data)
        
        if not config.USE_REQUEST:
            log.INFO(f"META: Shutting down Selenium Webdriver")
            # close webdriver very important
            driver.quit() # type: ignore
        
        # If book data is empty then the books is not a valid candidate for parsing
        end = time.time()
        log.INFO(f"META: Time taken for parsing: {"{:.2f}".format(end-start)}")
        return book_data
    
    def get_content(self, url: str, id: str) -> dict | None:
        """

        Args:
            url (string): content URL where the content for the book needs to be scraped from
            id (int): ebook_no used for logging purposes
        Returns:
            dict: It is a dictionary with keys ToC and Book_Content with the respective data
        """
        
        # run up the static page
        if config.USE_REQUEST:
            log.INFO(f"[{id}] Loading static HTML page via Python Requests")
            ps = self._get_responce(url, id)
        else:
            log.INFO(f"[{id}] Loading static HTML page via Selenuim Webdriver")
            driver = self._setup_driver()
            driver.get(url)
            sleep(3)
            ps = driver.page_source
        start = time.time()
        if ps and len(ps) > 256:
            soup = BeautifulSoup(ps, 'html.parser') 
        else:
            log.DEBUG(f"[{id}] Page is unparsable, lenght < 256")
            return None
        
        # scrap and parse the data from page
        log.INFO(f"[{id}] Scraping begin")
        parse_toc = ParseToc(soup, id)
        parse_ch = ParseChapters(soup, id)
        
        toc_data = parse_toc.parse_toc()
        log.INFO(f"[{id}] ToC scrapped")
        con_data = parse_ch.parse_webpage()
        log.INFO(f"[{id}] Content scrapped")
        
        log.INFO(f"[{id}] Scarping finished")
        # blind combine the two dictionaries
        book = {"ToC": toc_data, "Book_Content": con_data}
        end = time.time()
        log.INFO(f"[{id}] Time taken for parsing: {end - start}")
        return book        
