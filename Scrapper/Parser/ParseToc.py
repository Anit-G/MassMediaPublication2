import Utils.Central_Logger as log
class ParseToc:
    
    def __init__(self, beautifulsoup, id):
        self.soup = beautifulsoup
        self.id = id
    
    def _process_table_rows(self, table_rows: list) -> dict:
        """

        Args:
            table_rows (list): list of tr elements from the HTML page

        Returns:
            dict [{key: value}]: it is a dict of key value pairs where the key is the
            chapter number for all pairs value is the different chapter names
        """
        toc = {}        
        for idx, row in enumerate(table_rows):
            data = row.get_text(strip=True, separator=" ")
            toc[f"chapter_{idx}"] = data
        return toc
        
    def _identify_case(self):
        """
        Identifies the case based on the structure of the webpage.

        Args:
            soup (BeautifulSoup): Parsed HTML content.

        Returns:
            str: Identified case ("case1", "case2", "case3", "case4", "no_toc").
        """
        # Check for table inside allowed div classes
        allowed_classes = ["chapter", "content"]
        divs_with_allowed_classes = self.soup.find_all("div", class_=lambda c: c in allowed_classes)
        for div in divs_with_allowed_classes:
            if div.find("table"):
                log.INFO(f"[{self.id}] Found table inside a div element")
                return "case1"
        # Check for multiple tables and nearby headers with "content"
        # Most books should agree with this case
        tables = self.soup.find_all("table")
        for table in tables:
            header = table.find_previous(["h2", "h3", "h4"])
            if header and "content" in header.text.lower():
                log.INFO(f"[{self.id}] found a table post a header with \"content\" keyword")
                return "case2"

        # Check for divs with "content" header and paragraphs
        divs_with_chapters = self.soup.find_all("div", class_="chapter")
        for div in divs_with_chapters:
            header = div.find(["h2", "h3", "h4"])
            if header and "content" in header.text.lower() and div.find("p"):
                log.INFO(f"[{self.id}] found div with a header with \"content\" keyword and paragraph elements")
                return "case3"

        # Check for paragraphs with class "toc"
        toc_paragraphs = self.soup.find_all("p", class_="toc")
        if toc_paragraphs:
            log.INFO(f"[{self.id}] found paragraphs with toc classname")
            return "case4"

        # Default case: No ToC
        log.ERROR(f"[{self.id}] NO TOC found, please verify")
        return "no_toc"


    def _parse_case1(self):
        """
        Parses ToC for Case 1: Table inside allowed div classes.
        """
        allowed_classes = ["chapter", "content"]
        for div in self.soup.find_all("div", class_=lambda c: c in allowed_classes):
            table = div.find("table")
            if table:
                return self._process_table_rows(table.find_all("tr"))

    def _parse_case2(self):
        """
        Parses ToC for Case 2: Multiple tables, check headers.
        """
        tables = self.soup.find_all("table")
        for table in tables:
            header = table.find_previous(["h2", "h3", "h4"])
            if header and "content" in header.text.lower():
                return self._process_table_rows(table.find_all("tr"))
        # incase no table is found
        return []

    def _parse_case3(self):
        """
        Parses ToC for Case 3: Header with 'content' and paragraphs.
        """
        for div in self.soup.find_all("div", class_="chapter"):
            header = div.find(["h2", "h3", "h4"])
            if header and "content" in header.text.lower():
                return self._process_table_rows(div.find_all("p"))

    def _parse_case4(self):
        """
        Parses ToC for Case 4: Paragraphs with class "toc".
        """
        toc_paragraphs = self.soup.find_all("p", class_="toc")
        return self._process_table_rows(toc_paragraphs)

    def parse_toc(self):
        """
        Main function to parse the Table of Contents from a webpage.

        Args:
            url (str): Webpage URL.

        Returns:
            dict: {"chapter_#": chapter_name_value (string)} Parsed ToC or an error message. Toc is in the form of a
            dict of key value pairs where the key is always "chapter_#" and value is
            the actual chapter name.
        """
        # Load webpage using Selenium
        
        # Identify case
        log.INFO(f"[{self.id}] Determine case for scraping ToC")
        case = self._identify_case()
        log.INFO(f"[{self.id}] Identified Case: {case}")
        
        # Parse based on case
        if case == "case1":
            return self._parse_case1()
        elif case == "case2":
            return self._parse_case2()
        elif case == "case3":
            return self._parse_case3()
        elif case == "case4":
            return self._parse_case4()
        else:
            return {"ERROR": "SOMETHING WENT REALLY WRONG OR MISSING TOC"}