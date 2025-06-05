import csv
import logging

from pathlib import Path
from elibrary_parser.types import Publication

class PublicationSerializer:
    
    logger = logging.getLogger(__name__)
    def __init__(self, org_id, data_path = 'data/'):
        self.org_id = org_id
        self.data_path = Path(data_path)
        self.files_dir = None
        
        self.create_processed_dir()
        
    def create_processed_dir(self):
        (self.data_path / 'processed').mkdir(exist_ok=True, parents=True)
        
    def save_publications_to_csv(self, publications: list[Publication]):
        output_dir = self.data_path / 'processed' / self.org_id
        output_dir.mkdir(exist_ok=True)
        csv_path = output_dir/ 'publications.csv'
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(["Authors", "Title", "Year", "Source title", "Cited by", "Link", "Source ID"])
            for pub in publications:
                writer.writerow([
                    pub.authors,
                    pub.title,
                    pub.year,
                    pub.info,
                    pub.cited_by,
                    pub.link,
                    pub.source_id
                ])
            self.logger.info(f"Publications for organization {self.org_id} saved to: {csv_path}")
            