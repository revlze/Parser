import re
import time
import random
import logging

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from elibrary_parser import config
from elibrary_parser import logging_config

class Downloader:
    
    USER_AGENTS = (
        'Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML,like Gecko) Iron/28.0.1550.1 Chrome/28.0.1550.1',
        'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.16',
    )
    logger = logging.getLogger(__name__)
    
    def __init__(self, org_id, data_path = 'data/', headless=True):
        self.org_id = org_id
        self.data_path = Path(data_path)
        self.headless = headless
        self.driver = None
        self.files_dir = None
        self.driver_path = config.DRIVER_PATH
            
    def setup(self):
        options = Options()
        options.headless = self.headless
        options.set_preference("general.useragent.override", random.choice(self.USER_AGENTS))
        service = Service(executable_path=self.driver_path)
        self.driver = webdriver.Firefox(service=service,options=options)
        
    def __enter__(self):
        self.setup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
        
    def create_raw_dir(self):
        (self.data_path / 'raw').mkdir(exist_ok=True, parents=True)
        
        self.files_dir = self.data_path / 'raw' / self.org_id
        self.logger.info(f'Organization directory: {self.files_dir.absolute()}')
        self.files_dir.mkdir(exist_ok=True, parents=True)
        
    def _get_page_source(self, url):
        self.driver.get(url)
        self.logger.info(f"Navigated to URL: {url}")
        return self.driver.page_source
    
    def _save_current_page(self, page_number : int, source: str):
        file_path = self.files_dir / f"page_{page_number}.html"
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(source)
        self.logger.info(f"Saved page: {page_number} to {file_path}.")
    
    def _go_to_next_page(self) -> bool:
        try:
            self.bypass_block_if_present()
            self.driver.find_element(By.LINK_TEXT, 'Следующая страница').click()
            sleep_seconds = random.randint(2, 5)
            WebDriverWait(self.driver, 20).until(
                    EC.invisibility_of_element_located((By.ID, 'loading')))
            self.logger.info(f"Sleeping for {sleep_seconds} seconds before next page.")
            time.sleep(sleep_seconds)
            return True
        except NoSuchElementException:
            self.logger.warning("No more pages found!")
            return False
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {e}")
            return False
        
        
    def find_publications(self):
        
        org_page_url = f'https://www.elibrary.ru/org_items.asp?orgsid={self.org_id}'
        self.logger.info(f"Starting publication search for organization ID: {self.org_id}")

        self.logger.info(f"Navigating to organization page URL: {org_page_url}. (expecting about 1 min wait)")
        current_page_source = self._get_page_source(org_page_url)
        self.logger.info("Successfully loaded organization page.")

        self.bypass_block_if_present()
        
        self.enable_parameters()
        
        self.bypass_block_if_present()
        
        page_number = 1
        while True:
            self._save_current_page(page_number, self.driver.page_source)
            
            if not self._go_to_next_page():
                break
            
            page_number += 1
            
    def enable_parameters(self):
        self.logger.info("Enabling search parameters...")
        params = ['rubrics', 'titles', 'orgs', 'authors', 'years', 'types', 'roles', 'orgroles']
        selection_made = [self.chose_span(something=param) for param in params]
        params = ['orgdepid', 'show_option', 'show_sotr', 'sortorder', 'order']
        for param in params:
            selection_made.append(self.chose_select_option(select_id=param))
        selection_made.append(self.select_checkbox_options())
        if any(selection_made):
            try:
                self.driver.find_element(By.XPATH, "//div[@class='butred' and contains(text(), 'Поиск')]").click()
                self.logger.info("Successfully clicked the 'Поиск' button.")
                WebDriverWait(self.driver, 20).until(
                    EC.invisibility_of_element_located((By.ID, 'loading')))
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while clicking the 'Поиск' button: {e}")
                raise
        else:
            self.logger.warning("No search parameters selected. Skipping 'Поиск' button click.")
        
        
    def click_checkbox_by_id(self, checkbox_id: str) -> bool:
        xpath = f'//*[@id="{checkbox_id}"]'
        try:
            element = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            self.logger.error(f"An error occurred while trying to click checkbox! Exception: {e}")
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
            self.logger.error(f"An error occurred while getting checkbox options: {e}")
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
            self.logger.info(f'Option {name_to_select}')
            time.sleep(2)
            return True
        except Exception as e:
            self.logger.error(f'An error occurred while interacting with <select> ID {select_id}: {e}')
            return False

    
    # orgdepid, show_option, show_sotr, sortorder, order
    def get_select_option(self, select_id : str) -> dict:
        """
        Parses options from a dropdown (select) and logs them to the console.
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
                self.logger.warning(f'No availble options for {select_id}.')
                return {}
            
            for key, option in enumerate(options):
                option_value = option.get_attribute("value")
                option_text = option.text.strip()
                if option_value:
                    available_options[key] = {"name": option_text, "value" : option_value}
                    print(f'[{key}] {option_text}')
            return available_options
        except Exception as e:
            self.logger.error(f'An error occurred while getting options for <select> ID {select_id}: {e}')
            return {}
    
    def chose_select_option(self, select_id : str) -> bool:
        
        usr_input = input(f"Do you need to choose an option for {select_id}? (y/N) ")
        if usr_input.lower() not in {'y', 'yes'}: return False
        
        available_options = self.get_select_option(select_id)
        usr_input = input(f'\nEnter the option number for {select_id} (-1 if no selection needed): ')
        if usr_input == '-1': return False
        
        try:
            chosen_key = int(usr_input)
            if chosen_key in available_options:
                value_to_select = available_options[chosen_key]['value']
                name_to_select = available_options[chosen_key]['name']
                return self.select_option_by_id(select_id, value_to_select, name_to_select)
        except Exception as e:
            self.logger.error(f"An error occurred during option selection: {e}")
            return False
                
    # hdr_rubrics, hdr_titles, hdr_orgs, hdr_authors, hdr_years, hdr_types, hdr_roles, hdr_orgroles
    def get_span(self, something : str) -> dict:
        try:
            self.driver.find_element(By.ID, f"hdr_{something}").click()
            time.sleep(3)
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
                    self.logger.error("Exception: ", e)
            return available_something
        except Exception as e:
            self.logger.error(f"\nFailed to open {something} selection: {e}")
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
                self.logger.info(f"Selected {something}: [{key}]")
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

    
    def bypass_block_if_present(self):
        try:
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'recaptcha')]"))
            )
            print()
            self.logger.warning("Pass the captcha and press enter")
            input()
            self.logger.info("Blocking successfully passed!")
        except Exception:
            self.logger.info("Blocking is not detected or could not be bypassed - continue!")
    
