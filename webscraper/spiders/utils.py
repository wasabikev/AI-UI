from bs4 import BeautifulSoup

def clean_html(soup):
    if soup is None:
        print("Received None soup object")
        return "No content"

    try:
        # Remove script and style elements
        elements_to_remove = ["script", "style", "header", "footer", "nav", "form"]
        for tag in elements_to_remove:
            for element in soup.find_all(tag):
                element.decompose()

        # Get text and strip whitespace
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        clean_text = '\n'.join(line for line in lines if line)
        return clean_text # Used for converting to JSON and/or pairing with metadata
    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return "Error during HTML cleaning"

def extract_metadata(soup):
    metadata = {}
    try:
        # Extract the title
        title_tag = soup.find('title')
        metadata['title'] = title_tag.text.strip() if title_tag else "No title found"

        # Extract meta description
        description_tag = soup.find('meta', attrs={'name': 'description'})
        metadata['description'] = description_tag['content'].strip() if description_tag and description_tag.has_attr('content') else "No description found"

        # Add more metadata extraction logic here...
        # Rich Metadata Extraction: Extract other useful metadata like Open Graph tags, Twitter cards, canonical links, keywords, etc.
        # Dynamic Content Handling: Some metadata might be loaded dynamically via JavaScript. Consider integrating solutions like Selenium or Puppeteer if static scraping doesn't suffice.
        # Scalability: As the complexity of metadata extraction increases, consider optimizing the function to handle large volumes of pages efficiently.
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        metadata['error'] = "Error extracting metadata"

    return metadata