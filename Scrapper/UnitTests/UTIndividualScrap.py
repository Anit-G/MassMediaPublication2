import json
import time
# import asyncio
# import aiohttp
import requests
import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps
from Parser.ParserSetup import ParserSetup

def check_content(book_content):
    if(("ToC" in book_content) and ("Book_Content" in book_content)):
        if((len(book_content["ToC"]) > 1) and (len(book_content))>1):
            return True
    return False

def test_individual():
    log.INFO("UNIT TESTING BEGINS")
    parser_setup = ParserSetup()
    with open(config.TEST_LIST_FILE_PATH, 'r') as file:
        for line in file:
            ebook_no = line.strip('\n')
            log.INFO(f"UNITTEST: [{ebook_no}]")
            print(f"Running Unitest for book [{ebook_no}]")
            with DBOps() as db:
                content_url = db.get_content_url(int(ebook_no))
            book_content =  parser_setup.get_content(content_url, ebook_no)

            # write to filesystem
            path = "./Tests/test_" + str(ebook_no) + ".json"
            with open(path, 'w', encoding="utf-8") as f:
                json.dump(book_content, f, ensure_ascii=False, indent=4)
            f.close()
            
            if(check_content(book_content)):
                print("OK")
                print("-------------------------------------------------")
            else:
                print("KO")
                print("-------------------------------------------------")
                
    file.close()
    log.INFO("UNIT TESTING ENDS")