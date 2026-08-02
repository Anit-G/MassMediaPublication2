import Utils.Central_Logger as log
from bs4.element import Tag

class ParseChapters:
    
    def __init__(self, beautifulsoup, id):
        self.soup = beautifulsoup
        self.id = id
        log.INFO(f"[{self.id}]: Processing chapters for Ebook No. {self.id}")
        
        for br in self.soup.find_all("br"):
            br.replace_with("\r\n" + br.text)
        
    def check_repeating_headers(self, chapters: list) -> tuple[bool, set]:
        """
        Checks if there are repeating headers in the chapters data.

        Args:
            chapters (list): A list of dictionaries with keys 'header' and 'content'.
                            Example: [{"header": "Chapter 1", "content": ["..."]}, ...]

        Returns:
            bool: True if there are repeating headers, False otherwise.
            set: The set of duplicate headers, if any.
        """
        log.INFO(f"[{self.id}]: Checking for repeating chapter headings")
        headers = [chapter['header'] for chapter in chapters if chapter['header']]
        unique_headers = set(headers)
        
        if len(headers) != len(unique_headers):  # Check for duplicates
            # Identify duplicate headers
            duplicates = {header for header in unique_headers if headers.count(header) > 1}
            log.INFO(f"[{self.id}] Duplicate chapter headers found")
            return True, duplicates
        return False, set()
    
    def _is_header(self, tag: Tag) -> bool:
        return tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    
    def _is_valid_header(self, tag: Tag) -> bool:
        head_tag = tag.get_text(separator = '\n',strip=True)
        if "content" in head_tag.lower():
            return False
        # check if it is fluff
        if "The Project Gutenberg" in head_tag:
            return False
        if "illus" in head_tag.lower():
            return False
        return True
    
    def _is_valid_chapter(self, chapter) -> bool:
        # check is header has cont, illus 
        for tag in chapter.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            return self._is_valid_header(tag)        
        return True 
    
    def _parse_case1(self):
        chapters = {}
        # Iterate through div elements
        for idx, chapter in enumerate(self.soup.find_all("div", class_="chapter")):
            if(self._is_valid_chapter(chapter)):
                chp = {}
                para = []
                head_pt = 0
                #iterate through subtags of div tag
                for _, tag in enumerate(chapter.children):
                    if(tag != '\n'):
                        # at this point it is either a header or a paragraph within the chapter
                        if(self._is_header(tag)):
                            chp[f"header_{head_pt}"] = tag.get_text(separator = '\n',strip=True)
                            head_pt += 1
                        else:
                            p = tag.get_text(separator = '\n',strip=True)
                            if(p != ""):
                                para.append(p)
                                                    
                # get all the paragraphs between the div tags
                for sib in chapter.find_next_siblings():
                    if sib.name == 'p' and sib.get("class") != ['toc']:
                        p = sib.get_text(separator = '\n',strip=True)
                        if(p != ""):
                            para.append(p)
                    if sib.name == 'div' and 'chapter' in sib.get("class", []):
                        break
                # Consolidate the extra chapter headers
                header = []
                for key in list(chp.keys()):
                    if key != "content":
                        header.append(chp[key].strip())
                        chp.pop(key, None)
                chp["header"] = " ".join(header)
                chp["content"] = para
                chapters[f"chapter_{idx}"] = chp
        return chapters

    def _parse_case2(self):
        """
        Incases where the HTML page stores the content of the book as a list of headers and paragraph elements.
        Iterating through the elements we store the current header and append paras to current content when the next header is encountered
        All this information is combined as a single chapter so current header + current content. Incase of subheadings or multiple
        concurrent header where the last header is H all headers [0, H-1] are appended to chapters without content in solitude.
        
        Last chapter is the end case is handled seperately.

        Returns:
            Dict: {Chapter_#: {header: value, content: value}}
        """
        chapters = {}
        current_header = None
        current_idx = 0
        current_content = []

        for element in self.soup.find_all(['h1',"h2", "h3", "p", "pre"]):  # Adjust tags as needed
            if self._is_header(element):
                if current_header or current_content: 
                    chapters[f"chapter_{current_idx}"] = {
                        "header": current_header,
                        "content": current_content
                    }
                if self._is_valid_header(element):
                    text = [t.strip() for t in element.find_all(string=True) if t.parent.name !='span']
                    current_header = " ".join(filter(None, text))
                    current_idx += 1
                else:
                    current_header = None
                current_content = []
            elif element.name == "p" and current_header and element.get("class") != ['toc']:
                p = element.get_text(separator = '\n',strip=True)
                if(p != ""):
                    current_content.append(p)
            elif element.name == "pre":
                p = element.get_text(separator = '\n',strip=True)
                if(p != ""):
                    current_content.append(p)
        
        # Add the last chapter
        if current_header or current_content:
            chapters[f"chapter_{current_idx+1}"] = {
                "header": current_header,
                "content": current_content
            }
        return chapters

    def _determine_case(self):
        # Example heuristics for case determination
        if self.soup.find("div", class_="chapter"):
            log.INFO(f"[{self.id}] found div elements with class name chapter, no paragraphs present")
            return 1
        else:
            log.INFO(f"[{self.id}] no div with class name chapter, assuming page made of headers and conocurrent paragraphs")
            log.DEBUG(f"[{self.id}] This is the default case it might be the cause of the error")
            return 2

    def parse_webpage(self):
        """
        Raises:
            ValueError: if no case fits, which is impossible

        Returns:
            dict: {"chapter_#":{"header": value (string), "content": value (string)}} dict of chapters where each element is a dictionary
            of headers and content keys and their respective values.
        """
        log.INFO(f"[{self.id}] Start determining case for chapter scraping")
        case = self._determine_case()
        log.INFO(f"[{self.id}] proceed with parsing according to case: {case}")
        if case == 1:
            return self._parse_case1()
        elif case == 2:
            return self._parse_case2()
        else:
            return ValueError("Unknown structure. Parsing failed.")
