from pathlib import Path
import random
import time
import csv
import bs4
import re

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait, Select
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

    def __init__(self, org_id: str, data_path: str):
        self.org_id = org_id
        self.data_path = Path(data_path)
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
        print("Done.")
        
        self.bypass_block_if_present()
        
        self.enable_parameters()
        
        page_number = 1
        while True:
            with open(self.files_dir / f"page_{page_number}.html", 'w', encoding='utf-8') as f:
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
    
    def enable_parameters(self):
        params = ['rubrics', 'titles', 'orgs', 'authors', 'years', 'types', 'roles', 'orgroles']
        selection_made = [self.chose_span(something=param) for param in params]
        params = ['orgdepid', 'show_option', 'show_sotr', 'sortorder', 'order']
        for param in params:
            selection_made.append(self.chose_select_option(select_id=param))
        selection_made.append(self.select_checkbox_options())
        if any(selection_made):
            try:
                self.driver.find_element(By.XPATH, "//div[@class='butred' and contains(text(), 'Поиск')]").click()
                print("\nSuccessfully clicked the 'Поиск' button.")
                time.sleep(2)
            except Exception as e:
                print(f"An unexpected error occurred while clicking the 'Поиск' button: {e}")
                raise
        
        
    
    def click_checkbox_by_id(self, checkbox_id: str) -> bool:
        xpath = f'//*[@id="{checkbox_id}"]'
        try:
            element = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            print(f"An error occurred while trying to click checkbox! Exception: {e}")
            return False
    
    def select_checkbox_options(self) -> bool:
        
        check_show_refs = input("\n[ ] - учитывать публикации, извлеченные из списков цитируемой литературы? (y/N): ").lower() in {'y', 'yes'}
        check_hide_doubles = input("\n[✓] - объединять оригинальные и переводные версии статей и переиздания книг? (Y/n): ").lower()  in {'n', 'no'}
        
        if not check_hide_doubles and not check_show_refs:
            return False
        try:
            if check_hide_doubles:
                self.click_checkbox_by_id('check_hide_doubles')
            if check_show_refs:
                self.click_checkbox_by_id('check_show_refs')
            return True
        except Exception as e:
            print(f"An error occurred while getting checkbox options: {e}")
            return False
    
    
    def select_option_by_id(self, select_id: str, value_to_select: str, name_to_select: str) -> bool:
        """
        Selects an option in a dropdown (select) by its ID and the option's value.
        :param select_id: ID of the <select> element (e.g., 'orgdepid', 'show_option')
        :param value_to_select: The 'value' attribute of the <option> (e.g., '1', '2' etc.)
        :param name_to_select: The 'name' attribute of th <option> (e.g. 'Университет Иннополис', 'Факультет компьютерных и инженерных наук')
        :return: True if the option was successfully selected, False otherwise.
        """
        try:
            select_element = WebDriverWait(self.driver,timeout=10).until(
                EC.element_to_be_clickable((By.ID, select_id))
            )
            
            select_object = Select(select_element)
            select_object.select_by_value(value_to_select)
            print(f'Option {name_to_select}')
            time.sleep(2)
            return True
        except Exception as e:
            print(f'An error occurred while interacting with <select> ID {select_id}: {e}')
            return False

    
    # orgdepid, show_option, show_sotr, sortorder, order
    def get_select_option(self, select_id : str) -> dict:
        """
        Parses options from a dropdown (select) and prints them to the console.
        Returns a dictionary where the key is a sequential number and the value is the dictionary with option's name and value.

        :param select_id: ID of the <select> element (e.g., 'orgdepid', 'show_option')
        :return: A dictionary of available options.
        """
        try:
            select_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, select_id))
            )
            available_options = {}
            print(f"\nAvailable options for id = {select_id}:")
            # Find all option elements within this select
            options = select_element.find_elements(By.TAG_NAME, "option")
            if not options:
                print(f'No availble options for {select_id}.')
                return {}
            
            for key, option in enumerate(options):
                option_value = option.get_attribute("value")
                option_text = option.text.strip()
                if option_value:
                    available_options[key] = {"name": option_text, "value" : option_value}
                    print(f'[{key}] {option_text} (value: {option_value})')
            return available_options
        except Exception as e:
            print(f'An error occurred while getting options for <select> ID {select_id}: {e}')
            return {}
    
    def chose_select_option(self, select_id : str) -> bool:
        
        usr_input = input(f"Do you need to choose an option for {select_id}? (y/N) ")
        if usr_input.lower() not in {'y', 'yes'}: return False
        
        available_options = self.get_select_option(select_id)
        usr_input = input(f'\nEnter the option nuber for {select_id} (-1 if no selection needed): ')
        if usr_input == '-1': return False
        
        try:
            chosen_key = int(usr_input)
            if chosen_key in available_options:
                value_to_select = available_options[chosen_key]['value']
                name_to_select = available_options[chosen_key]['name']
                return self.select_option_by_id(select_id, value_to_select, name_to_select)
        except Exception as e:
            print(f"An error occurred during option selection: {e}")
            return False
                
    # hdr_rubrics, hdr_titles, hdr_orgs, hdr_authors, hdr_years, hdr_types, hdr_roles, hdr_orgroles
    def get_span(self, something : str) -> dict:
        try:
            self.driver.find_element(By.ID, f"hdr_{something}").click()
            time.sleep(6)
            WebDriverWait(self.driver, timeout=6).until(
                EC.visibility_of_element_located((By.ID, f"{something}_options"))
            )
            something_rows = self.driver.find_elements(
                By.XPATH,
                f'//div[@id="{something}_options"]//table[@id="{something}_table"]/tbody/tr')
            available_something = {}
            print(f"Available {something} ( [key_number] {something} (number of publications) ):")
            for key, row in enumerate(something_rows):
                try:
                    tds = row.find_elements(By.TAG_NAME, "td")
                    if len(tds) != 2: continue
                    
                    input_element = tds[0].find_element(By.TAG_NAME, "input")
                    checkbox_id = input_element.get_attribute("id")
                    
                    text = tds[1].text.strip()  
                    m = re.match(r'(.+?)\s*\((\d+)\)\s*$', text)
                    if m:
                        available_something[key] = checkbox_id
                        print(f'[{key}] {m.group(0)}')
                except Exception as e:
                    print("Exception: ", e)
            return available_something
        except Exception as e:
            print(f"\nFailed to open {something} selection: {e}")
            return {}
            
    
    def chose_span(self, something) -> bool:
        usr_input = input(f"Need a choice of {something} in the parameters? (y/N) ")
        if usr_input.lower() not in {'y', 'yes'}: return False
        available_something = self.get_span(something)
        
        usr_input = input(f"\nEnter key numbers (-1 if no span needed): ")
        if usr_input == '-1': return False
        for key in self.parse_ranges(usr_input):
            checkbox_id = available_something[key]
            if self.click_checkbox_by_id(checkbox_id):
                print(f"Selected {something}: [{key}]")
        return True
        
    @staticmethod
    def parse_ranges(usr_input : str) -> set:
        res = set()
        for part in re.finditer(r'\s*(\d+)(?:\s*-\s*(\d+))?\s*', usr_input):
            start = int(part.group(1))
            end = int(part.group(2)) if part.group(2) else start
            for i in range(start, end+1):
                res.add(i)
        return res
    
        
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
        return italic[0].text.replace(',', ';') if italic else ParserOrg.missing_value

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
        html_files = sorted(self.files_dir.glob("page_*.html"), key=lambda f: int(f.stem.split('_')[1]))
        print("Parsing publications for organization", self.org_id)
        for file in html_files:
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

        
    # Authors,Title,Year,Source title,Cited by,Link
    def save_publications_to_csv(self):
        """Save organization's publications to a csv-file"""
        
        output_dir = self.data_path / "processed" / self.org_id
        output_dir.mkdir(exist_ok=True)
        csv_path = output_dir / "publications.csv"

        with open(csv_path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(["Authors", "Title", "Year", "Source title", "Cited by", "Link"])
            for pub in self.publications:
                writer.writerow([
                    pub.authors, pub.title, pub.year, pub.info, pub.cited_by, pub.link
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
