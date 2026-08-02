import json
import Utils.Config_vars as config
import Utils.Central_Logger as log

from Utils.DB_Operations import DBOps
from Scrapper.Parser.ParserSetup import ParserSetup

def meatadata_scraper() -> None:
    DBInstance = DBOps()
    parser_setup = ParserSetup()
    book_list = DBInstance.get_book_source_urls()
    for i in range(len(book_list)): 
        url = book_list[i][0]
        log.INFO(f"META: Processing URL: {url}")
        book_metadata = parser_setup.get_metadata(url)
        if book_metadata:
            # Book needs to be parsed
            log.INFO(f"META: [{book_metadata['ebook_no']}] Book is pressed for further parsing")
            book_metadata['status'] = "PARSEABLE"
            DBInstance.update_meta_state(book_metadata) 
        else:
            # Book needs to be removed
            log.DEBUG(f"META: [{url.split('/')[-1]}] Book failed, request error or filteration")

def content_scrapper(category: str) -> int:
    DBInstance = DBOps()
    book_list = DBInstance.get_parseable_books(category)
    parser_setup = ParserSetup()

    for i in range(len(book_list)):
        ebook_no = book_list[i][0]
        current_url = book_list[i][1]
        no_rating = book_list[i][3]
        log.INFO(f"Scrapper[{ebook_no}]: Starting scrapping for book content {current_url}")
        
        book_content = parser_setup.get_content(current_url, ebook_no)
        if book_content:
            # write to filesystem
            path = config.JSON_FILEPATH + "/book_" + str(ebook_no) + ".json"
            with open(path, "w", encoding="utf-8") as file:
                json.dump(book_content, file, ensure_ascii=False, indent=4)
            # Update in DB that this was already parsed
            DBInstance.update_status_meta(ebook_no, "PARSED")
            DBInstance.insert_new_book(ebook_no, category, no_rating)
        else:
            DBInstance.update_status_meta(ebook_no, "UNPARSED")
    return 1

if __name__ == "__main__":
    log.INFO("START OF PROGRAM: HONEYFIDDLESTICKS")
    for i in range(100):
        try:
            for c in ["cat(RS)","cat(TA)","cat(MS)","cat(WE)","cat(LM)"]:
                content_scrapper(c)
        except  Exception as e:
            log.ERROR(f"Error occured: {e} continue loop")
            continue