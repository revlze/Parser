from pathlib import Path
import random
import time
import csv
import bs4

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from elibrary_parser import config
from elibrary_parser.types import Publication

class ParserOrg:
    """Class for loading and processing publications by eLibrary authors

     Attributes
     -----------
     driver: WebDriver
        Firefox browser driver
        Set by method: setup_webdriver

     publications: lst
        A list with info for each author
        Set by method: save_publications

     author_id: str
        elibrary identificator

     data_path: Path
        a path where all data stored

     date_to, date_from: int
        dates (including extremities) within which search will be processed
     """
     
    USER_AGENTS = (
        'Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML,like Gecko) Iron/28.0.1550.1 Chrome/28.0.1550.1',
        'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.16',
    )
    DRIVER_PATH = config.DRIVER_PATH
    missing_value = '-'

    def __init__(self, org_id: str, data_path: str, date_from: int, date_to: int):
        self.org_id = org_id
        self.data_path = Path(data_path)
        self.date_from = date_from
        self.date_to = date_to
        self.driver = None
        self.files_dir = None
        self.publications = []

        self.create_files_dir()
        self.setup_webdriver()

    def setup_webdriver(self):
        """Settings for a selenium web driver
        Changes a self.driver attribute"""

        new_useragent = random.choice(self.USER_AGENTS)

        profile = webdriver.FirefoxProfile()
        profile.set_preference("general.useragent.override", new_useragent)
        options = Options()
        options.headless = False

        self.driver = webdriver.Firefox(
            profile, executable_path=self.DRIVER_PATH, options=options)

    def create_files_dir(self):
        """Creates directory for the web-pages of an specific organization"""
        
        (self.data_path / "raw").mkdir(exist_ok=True, parents=True)
        (self.data_path / "processed").mkdir(exist_ok=True, parents=True)

        self.files_dir = self.data_path / "raw" / self.org_id
        print("Organization directory:", self.files_dir.absolute())
        self.files_dir.mkdir(exist_ok=True, parents=True)

    def find_publications(self):
        """Gets the web-page with chosen years and chosen...(will be added soon)"""
        
        org_page_url = f'https://www.elibrary.ru/org_items.asp?orgsid={self.org_id}'
        print(f"Organization page URL: {org_page_url}.")
        
        print("Wait, getting organization page...(about 1 min)")
        self.driver.get(org_page_url)
        time.sleep(60)
        print("Done.")
        
        self.bypass_block_if_present()
        
        # Write 9999 in the script in the years field if you don't need this filter
        if (self.data_from != 9999 and self.data_to != 9999):
            print("Choosing years...")
            try:
                self.driver.find_element(By.XPATH, '//*[@id="hdr_years"]').click()
                time.sleep(5)
            except Exception as e:
                print("Failed to open year selection:", e)

            for year in range(self.date_from, self.date_to + 1):
                xpath = f'//*[@id="year_{year}"]'
                try:
                    element = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, xpath)))
                    self.driver.execute_script("arguments[0].click();", element)
                    print("Selected year:", year)
                except Exception:
                    print(f"Can't load the year selection or no publications for: {year} year!")


            #Click "search" button
            self.driver.find_element(By.XPATH, '//td[6]/div').click() # TODO: remove hardcoded index
            
            
        page_number = 1
        while True:
            with open(self.files_dir / f"page_{page_number}.html", 'a', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print(f"Saved page: {page_number}.")

            try:
                self.bypass_block_if_present()
                self.driver.find_element(
                    By.LINK_TEXT, 'Следующая страница').click()
                
                page_number += 1
                sleep_seconds = random.randint(10, 20)
                print(f"Sleeping for {sleep_seconds} seconds.")
                time.sleep(sleep_seconds)
            except NoSuchElementException:
                print("No more pages!")
                break

    @staticmethod
    def create_table_cells(soup):
        publications_table = soup.find_all('table', id="restab")[0]
        
        for box in publications_table.find_all('table', width="100%", cellspacing="0"):
            box.decompose() # Remove all inner tags
            
        return publications_table.find_all('td', align="left", valign="top")

    @staticmethod
    def get_title(cell: bs4.element.ResultSet) -> str:
        """Get publication titles from an HTML page box

        Parameters:
        -----------
        cell : bs4.element.ResultSet
        """
        
        span = cell.find_all('span', style="line-height:1.0;")
        return span[0].text if span else ParserOrg.missing_value

    @staticmethod
    def get_authors(cell: bs4.element.ResultSet) -> str:
        """Get authors from an HTML page box"""
        
        font = cell.find_all('font', color="#00008f")
        if not font:
            return ParserOrg.missing_value
        italic = font[0].find_all('i')
        return italic[0].text.replace(',', ';').lower() if italic else ParserOrg.missing_value

    @staticmethod
    def get_info(cell: bs4.element.ResultSet) -> str:
        """Get journal info from an HTML page box"""
        
        if not cell:
            return ParserOrg.missing_value
        
        fonts = cell.find_all("font", color="#00008f")

        if len(fonts) < 2:
            return ParserOrg.missing_value
        
        biblio_info = fonts[1].get_text(strip=True)
        biblio_info = biblio_info.replace('\xa0', ' ').replace('\r\n', ' ').replace('\n', ' ')
        return biblio_info

    @staticmethod
    def get_link(cell: bs4.element.ResultSet) -> str:
        """Get article link from an HTML page box"""
        
        links = cell.find_all('a')
        if not links:
            return ParserOrg.missing_value
        
        return 'https://www.elibrary.ru/' + links[0].get('href')
    
    @staticmethod
    def get_cited_by(cell: bs4.element.ResultSet) -> str:
        """Get the number of citations of an article from an HTML page box"""
        
        tds = cell.find_parent("tr").find_all("td")
        return tds[2].get_text(strip=True)
        

    def parse_publications(self):
        """ Get trough the html file and save information from it"""
        
        print("Parsing publications for organization", self.org_id)
        for file in self.files_dir.glob("*.html"):
            print(f"Reading {file.name}...")
            with open(file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            for cell in self.create_table_cells(soup):
                info = self.get_info(cell)
                pub = Publication(
                    title=self.get_title(cell),
                    authors=self.get_authors(cell),
                    info=info,
                    link=self.get_link(cell),
                    cited_by=self.get_cited_by(cell),
                )
                pub.get_year()
                self.publications.append(pub)

        
    # Authors,Title,Year,Source title,Cited by
    def save_publications_to_csv(self):
        """Save organization's publications to a csv-file"""
        
        output_dir = self.data_path / "processed" / self.org_id
        output_dir.mkdir(exist_ok=True)
        csv_path = output_dir / "publications.csv"

        with open(csv_path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(["Authors", "Title", "Year", "Source title", "Cited by"])
            for pub in self.publications:
                writer.writerow([
                    pub.authors, pub.title, pub.year, pub.info, pub.cited_by
                ])
                
                
    def bypass_block_if_present(self):
        try:
            checkbox = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[3]/div[1]/div/div/span/div[1]"))
            )
            checkbox.click()
    
            continue_button = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/form/input[2]"))
            )
            continue_button.click()

            print("Blocking successfully passed!,")
        except Exception:
            print("Blocking is not detected or could not be bypassed - continue!")
