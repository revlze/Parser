import bs4
import re
import logging

from pathlib import Path
from bs4 import BeautifulSoup

from .types import Publication

class ElibraryHTMLParser:
    
    logger = logging.getLogger(__name__)
    
    def __init__(self, org_id, data_path = 'data/'):
        self.org_id = org_id
        self.data_path = Path(data_path)
        self.files_dir = self.data_path / 'raw' / self.org_id
        
    def parse_publications(self):
        """ Get trough the html file and save information from it"""
        publications = []
        unique_pubs = set()
        html_files = sorted(self.files_dir.glob("page_*.html"), key=lambda f: int(f.stem.split('_')[1]))
        self.logger.info(f"Parsing publications for organization '{self.org_id}'")
        for file in html_files:
            self.logger.info(f"Reading {file.name}...")
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
                    source_id=self.get_source_id(cell)
                )
                pub.get_year()
                if pub.authors != '-' and pub not in unique_pubs:
                    publications.append(pub)
                    unique_pubs.add(pub)
        return publications

    @staticmethod
    def create_table_cells(soup):
        publications_table = soup.find_all('table', id="restab")[0]

        for box in publications_table.find_all('table', width="100%", cellspacing="0"):
            box.decompose() # Remove all inner tags

        return publications_table.find_all('td', align="left", valign="top")

    @staticmethod
    def get_title(cell: bs4.element.ResultSet) -> str:
        """Get publication titles from an HTML page box      
        :param cell 
        :return: Title of publication
        """

        span = cell.find_all('span', style="line-height:1.0;")
        return span[0].text if span else Publication.missing_value

    @staticmethod
    def get_authors(cell: bs4.element.ResultSet) -> str:
        """Get authors from an HTML page box"""

        font = cell.find_all('font', color="#00008f")
        if not font:
            return Publication.missing_value
        italic = font[0].find_all('i')
        return italic[0].text.replace(',', ';') if italic else Publication.missing_value

    @staticmethod
    def get_info(cell: bs4.element.ResultSet) -> str:
        """Get journal info from an HTML page box"""

        if not cell:
            return Publication.missing_value

        fonts = cell.find_all("font", color="#00008f")

        if len(fonts) < 2:
            return Publication.missing_value

        biblio_info = fonts[1].get_text(strip=True)
        biblio_info = biblio_info.replace('\xa0', ' ').replace('\r\n', ' ').replace('\n', ' ')
        return biblio_info

    @staticmethod
    def get_link(cell: bs4.element.ResultSet) -> str:
        """Get article link from an HTML page box"""

        links = cell.find_all('a')
        if not links:
            return Publication.missing_value

        return 'https://www.elibrary.ru/' + links[0].get('href')

    @staticmethod
    def get_cited_by(cell: bs4.element.ResultSet) -> str:
        """Get the number of citations of an article from an HTML page box"""

        tds = cell.find_parent("tr").find_all("td")
        return tds[2].get_text(strip=True)
    
    @staticmethod
    def get_source_id(cell: bs4.element.ResultSet) -> str:
        try:
            fonts = cell.find_all("font", color="#00008f")
            link_tag = fonts[1].find('a')
            href = link_tag.get('href') 
            match = re.search(r'id=(\d+)', href or '')
            return 'https://www.elibrary.ru/contents.asp?id=' + match.group(1)
        except Exception:
            return Publication.missing_value