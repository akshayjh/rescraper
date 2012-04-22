import urllib2
from bs4 import BeautifulSoup
import re
import time
import logging
import unittest

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
    listing_ids = o.get_listing_ids()

    listing = Listing("1718302")
    import pprint
    pprint.pprint(listing.get_listing_detail())


class WebModel(object):
    """Abstract class which forms the base for each kind of retrievable model.

    Produces BeautifulSoup objects which remained cached for the lifetime of
    the object.

    Has throttleDelay to mitigate impact on the target web server.
    """

    html_cache = {}

    def __init__(self, throttleDelay=5):
        self.throttleDelay = throttleDelay

    def fetch_html_page(self, url):
        # fetch html page from the web
        try:
            return WebModel.html_cache[url]
        except KeyError:
            # Throttle if neccesary
            currentTime = time.time()
            if (hasattr(WebModel, 'lastRequestTime') and 
                currentTime - WebModel.lastRequestTime < self.throttleDelay):
                self.throttleTime = (self.throttleDelay -
                                     (currentTime - WebModel.lastRequestTime))
                logging.debug("ThrottlingProcessor: Sleeping for %s seconds" % self.throttleTime)
                time.sleep(self.throttleTime)
            WebModel.lastRequestTime = time.time()
            # Make a soup object from the specified url
            logging.debug("Fetching url: " + url)            
            WebModel.html_cache[url] = urllib2.urlopen(url).read()
            return WebModel.html_cache[url]
        finally:
            logging.debug("Returning cache: " + url)


class Office(WebModel):

    BASE_URL = "http://www.realestate.co.nz/profile/office/"

    def __init__(self, office_id, throttleDelay=5):
        WebModel.__init__(self, throttleDelay)
        self.office_id = office_id

    def get_office_details(self):
        office_url = get_listings_page_url(1)
        html_page = self.fetch_html_page(url)
        soup_page = BeautifulSoup(html_page)
        return get_office_details_from_soup(self, soup_page)

    def get_office_details_from_soup(self, soup_page):
        return {
            'name': get_name(soup_page),
            'address': get_address(soup_page),
            'phone': get_phone(soup_page),
            'website': get_website(soup_page),
            'position': get_position(soup_page),
        }

    def get_name(self, soup_page):
        return soup_page.find('div', id="office-details").h2.text

    def get_address(self, soup_page):
        return soup_page.find('div', id="office-details").li.text

    def get_phone(self, soup_page):
        phone_pattern = re.compile("Phone:([ 0-9]+)")
        result = soup_page.find('li', text=phone_pattern).text
        return re.match(phone_pattern, result).groups()[0].strip()

    def get_website(self, soup_page):
        return soup_page.find('a', text="View our website").get('href')

    def get_position(self, soup_page):
        pos_pattern = re.compile(r"position: new google.maps.LatLng\((-?[\.\d]+), (-?[\.\d]+)\)")
        result = soup_page.find('script', text=pos_pattern).text
        latlong = re.search(pos_pattern, result).groups()
        return {
            "lat": latlong[0].strip(),
            "long": latlong[1].strip(),
        }

    def get_listing_ids(self):
        # Iterates through all of the Listings summary pages for this
        # Office and returns a list of all Listing IDs
        page_number = 1
        listing_ids = []

        while True:
            url = self.get_listings_page_url(page_number)
            html_page = self.fetch_html_page(url)
            soup_page = BeautifulSoup(html_page)
            listing_ids.append(get_listing_ids_from_soup(soup_page))
            if self.is_last_page(soup_page):
                break
            page_number += 1

        return listing_ids

    def get_listing_ids_from_soup(self, soup_page):
        # Extracts and returns all of the Listing IDs from a single soup page.
        listing_ids = []

        for listing_element in soup_page.find_all('div', {'class': 'listing'}):
            # listing ID is contained in the 'id' tag of the listing div.
            listing_ids.append(self.extract_listing_id(listing_element['id']))
            logging.debug("Listings found: %d" % len(listing_ids))

        return listing_ids

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


class Listing(WebModel):

    BASE_URL = "http://www.realestate.co.nz/"

    def __init__(self, listing_id, throttleDelay=5):
        WebModel.__init__(self, throttleDelay)
        self.listing_id = listing_id

    def get_listing_detail(self):
        listing_details = {'listing id': self.listing_id}

        url = self.get_listing_url()
        listings_page = BeautifulSoup(url)

        headerDetails = listings_page.find('div', {'class': 'headerDetails'})
        listing_details['heading'] = headerDetails.find('h1').text
        listing_details['price'] = headerDetails.find('h3').contents[0].strip()

        breadcrumbs = listings_page.find(id='breadcrumbs')
        listing_details['address'] = [a.text for a in breadcrumbs.find_all('a')[1:]]

        description = listings_page.find('div', {'class': 'description detailsPage'})
        listing_details['description'] = description.p.text

        agency_details = listings_page.find('div', {'class': 'agencyDetailsBox'})
        listing_details['agency id'] = re.search(r'^.*?(\d+)$', agency_details.a['class'][0]).group()

        return listing_details

    def get_listing_url(self):
        # The url of the listing detail page.
        return "%s%s" % (self.__class__.BASE_URL, self.listing_id)


class WebModelTest(unittest.TestCase):

    def setUp(self):
        self.web_model = WebModel()
        self.test_url = "http://www.google.com"
        self.expected_content = "<!doctype html>"

    def test_defaults(self):
        self.assertEquals(self.web_model.throttleDelay, 5)

    def test_fetch_html_page(self):
        # check that the cache exists and is an empty dict
        self.assertEquals(WebModel.html_cache, {})
        # test that html pages can be retrieved from the web
        test_html = self.web_model.fetch_html_page(self.test_url)
        self.assertIn(self.expected_content, test_html)
        # check that the correct key has been created in the cache
        self.assertIn(self.test_url, WebModel.html_cache)
        # check that the correct html was cached
        self.assertEquals(WebModel.html_cache[self.test_url], test_html)


class OfficeTest(unittest.TestCase):

    def setUp(self):
        self.office = Office("12345")

        self.expected_office_details = {
            "id":"3551",
            "name":"Double Winkel Real Estate Ltd (Licensed: REAA 2008) - Professionals, Paremata",
            "address": "105 Mana Esplande, Paremata, WELLINGTON",
            "phone": "04 233 9955",
            "website": "http://www.doublerealestate.co.nz",
            "position": {
                "lat": "-41.09264",
                "long": "174.8684",
            },
        }

        self.expected_listings = [
            "1650249",
            "1644095",
            "1641265",
            "1641262",
            "1622767",
            "1617538",
            "1241981",
            "646581",
        ]

        # test page 1 of 2
        test_html = file("test_html/office_page1_test.html").read()
        self.test_soup_page1 = BeautifulSoup(test_html)
        # test page 2 of 2
        test_html = file("test_html/office_page2_test.html").read()
        self.test_soup_page2 = BeautifulSoup(test_html)

    def test_get_listings_page_url(self):
        expected_url = "http://www.realestate.co.nz/profile/office/12345/page1"
        self.assertEquals(self.office.get_listings_page_url(1), expected_url)
        expected_url = "http://www.realestate.co.nz/profile/office/12345/page2"
        self.assertEquals(self.office.get_listings_page_url(2), expected_url)
    
    def test_is_last_page_1(self):
        # test for a negative case
        self.assertFalse(self.office.is_last_page(self.test_soup_page1))

    def test_is_last_page_2(self):
        # test for a positive case
        self.assertTrue(self.office.is_last_page(self.test_soup_page2))

    def test_get_listing_ids_from_soup(self):
        found_listings = self.office.get_listing_ids_from_soup(self.test_soup_page2)
        self.assertEqual(found_listings, self.expected_listings)

    def test_get_name(self):
        name = self.office.get_name(self.test_soup_page1)
        self.assertEqual(name, self.expected_office_details['name'])
 
    def test_get_address(self):
        address = self.office.get_address(self.test_soup_page1)
        self.assertEqual(address, self.expected_office_details['address'])

    def test_get_phone(self):
        phone = self.office.get_phone(self.test_soup_page1)
        self.assertEqual(phone, self.expected_office_details['phone'])

    def test_get_website(self):
        website = self.office.get_website(self.test_soup_page1)
        self.assertEqual(website, self.expected_office_details['website'])

    def test_get_position(self):
        position = self.office.get_position(self.test_soup_page1)
        self.assertEqual(position, self.expected_office_details['position'])

            
if __name__ == '__main__':
    unittest.main()
