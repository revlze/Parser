
import logging
from elibrary_parser.downloader import Downloader
from elibrary_parser.html_parser import ElibraryHTMLParser
from elibrary_parser.serializer import PublicationSerializer
from elibrary_parser import logging_config # Просто чтобы убедиться, что логирование настроено

logger = logging.getLogger(__name__)

def run_scraper(org_id: str, headless: bool = True):
    logger.info(f"Starting scraping process for organization ID: {org_id}")

    with Downloader(org_id=org_id, data_path='data/', headless=headless) as downloader:
        downloader.create_raw_dir()
        downloader.find_publications()

    parser = ElibraryHTMLParser(org_id=org_id)
    publications = parser.parse_publications()

    serializer = PublicationSerializer(org_id=org_id)
    serializer.save_publications_to_csv(publications)

    logger.info(f"Scraping and processing for organization ID {org_id} completed successfully.")

if __name__ == "__main__":
    target_org_id = '14346'
    target_headless_mode = False

    run_scraper(target_org_id, target_headless_mode)