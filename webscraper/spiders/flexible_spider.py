import scrapy
import json
from bs4 import BeautifulSoup
from utils import clean_html, extract_metadata

class FlexibleSpider(scrapy.Spider):
    name = "flexible_spider"
    
    def __init__(self, url, allowed_domain='', *args, **kwargs):
        super(FlexibleSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url]
        self.allowed_domains = [allowed_domain]
        # Configure logging to avoid logs in stdout
        import logging
        logger = logging.getLogger('scrapy')
        logger.setLevel(logging.WARNING)

    def parse(self, response):
        soup = BeautifulSoup(response.text, 'html5lib')
        clean_text = clean_html(soup)
        metadata = extract_metadata(soup)

        # Prepare data as a JSON object
        data = {
            'content': clean_text,
            'metadata': metadata
        }
        # Yield the JSON data. 
        yield data

        # Print the data as a JSON string for debugging. 
        # print(json.dumps(data, ensure_ascii=False))