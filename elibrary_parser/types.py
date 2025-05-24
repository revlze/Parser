import re


class Publication:
    """ Storing information about publications
    Finds similarities between given authors

     Attributes
     ----------
     title: str
        publication title
     authors: str
        publication authors
     info: str
        publication info (journal, etc.)
     link: str
        link for the publication
    """

    def __init__(self, title: str, authors: str, info: str, link: str, cited_by: str):
        self.title = title
        self.authors = authors
        self.info = info
        self.link = link
        self.year = None
        self.cited_by = cited_by
        
    missing_value = '-'

    def to_csv_row(self) -> str:
        """ Create a table row with comma between the elements """

        return f'{self.authors},{self.title},{self.year},{self.info},{self.cited_by}'
    
    def get_year(self):
        """ Gets a year in the range from 1900 to 2100 """

        years = re.findall(r'20\d{2}|19\d{2}', self.info)
        if years:
            self.year = years[0]
        else:
            self.year = Publication.missing_value

    def __eq__(self, other) -> bool:
        """ Gets out any similar authors publications if their
        authors, title, info, link and year are equal

        Parameters:
        -----------
        other : Publication
            other info to compare with
        """

        return (
                self.title == other.title
                and self.authors == other.authors
                and self.info == other.info
                and self.link == other.link
                and self.year == other.year
                and self.cited_by == other.cited_by
        )

    def __hash__(self):
        """ Hashes a publication"""

        return hash(self.title) ^ hash(self.authors) ^ hash(self.info) ^ hash(self.link) ^ hash(self.year) ^ hash(self.cited_by)
