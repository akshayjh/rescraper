import urllib2
from bs4 import BeautifulSoup
import re
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

offices = {"Porirua": "3521",
           "Paremata": "3551",
           "Tawa": "3534",
           "Whitby": "3541",
           "Otaki": "1756",
           "Waikanae": "1703",
           "Paraparaumu": "1663",
           }

def main():
    o = Office("1663")
    o.get_listing_ids()
    o.get_listing_ids()


class Office(object):

    BASE_URL = "http://www.realestate.co.nz/profile/office/"

    def __init__(self, office_id):
        self.office_id = office_id

    def get_listing_ids(self):
        page_number = 1
        listing_ids = []

        while True:
            url = self.get_listings_page_url(page_number)
            listings_page = self.make_soup(url)
            logging.debug("page %d" % page_number)
            for listing_element in listings_page.find_all('div', {'class': 'listing'}):
                # listing ID is contained in the 'id' tag of the listing div.
                listing_ids.append(self.extract_listing_id(listing_element['id']))
            logging.debug("Listings found: %d" % len(listing_ids))
            if self.is_last_page(listings_page):
                break
            page_number += 1
        return listing_ids

    def make_soup(self, url, cache={}):
        try:
            return cache[url]
        except KeyError:
            logging.debug("Fetching url: " + url)
            # Make a soup object from the specified url
            cache[url] = BeautifulSoup(self.fetch_html_page(url))
            return cache[url]
        finally:
            logging.debug("Returning cache: " + url)

    def fetch_html_page(self, url):
        # fetch html page from the web
        return urllib2.urlopen(url).read()

    def get_listings_page_url(self, page_number):
        # The url of the office details page. These are paginated, so we must
        # iterated through the page numbers to retrieve all of the data.
        return "%s%s/page%d" % (self.__class__.BASE_URL, self.office_id, page_number)

    def is_last_page(self, soup_page):
        # checks for a "Next Page" link
        return not soup_page.find('a', text='Next Page')

    def extract_listing_id(self, text):
        # Get the numerical part of the listing ID only
        return re.search(r"\d+", text).group()


if __name__ == '__main__':
    main()
