import urllib2
from bs4 import BeautifulSoup
import os
import re
import time
import logging
import unittest

TEST_HTML_FOLDER = "test_html"

class WebModel(object):
    """Abstract class which forms the base for each kind of retrievable model.

    Produces BeautifulSoup objects which remained cached for the lifetime of
    the object.

    Has throttle_delay to mitigate impact on the target web server.
    """

    html_cache = {}

    def __init__(self, throttle_delay=5):
        self.throttle_delay = throttle_delay

    def fetch_html_page(self, url):
        ''' Fetch html page from the web.
        Employs caching so that the same url won't be retrived more than
        once unless the cache is cleared.
        Also has a throttle_delay to avoid hammering REINZ's webservers
        '''
        try:
            return WebModel.html_cache[url]
        except KeyError:
            # Throttle if neccesary
            current_time = time.time()
            if (hasattr(WebModel, 'last_request_time') and 
                current_time - WebModel.last_request_time
                < self.throttle_delay):
                self.throttle_time = (self.throttle_delay -
                    (current_time - WebModel.last_request_time))
                logging.debug(
                    "ThrottlingProcessor: Sleeping for %s seconds"
                    % self.throttle_time
                    )
                time.sleep(self.throttle_time)
            WebModel.last_request_time = time.time()
            # Make a soup object from the specified url
            logging.debug("Fetching url: " + url)            
            WebModel.html_cache[url] = urllib2.urlopen(url).read()
            return WebModel.html_cache[url]
        finally:
            logging.debug("Returning cache: " + url)


class Office(WebModel):

    BASE_URL = "http://www.realestate.co.nz/profile/office/"

    def __init__(self, office_id, throttle_delay=5):
        WebModel.__init__(self, throttle_delay)
        self.office_id = office_id

    def get_office_details(self):
        ''' Collect all details pertaining to this real estate office '''
        office_url = self.get_listings_page_url(1)
        html_page = self.fetch_html_page(office_url)
        soup_page = BeautifulSoup(html_page)
        return self.get_office_details_from_soup(soup_page)

    def get_office_details_from_soup(self, soup_page):
        return {
            'name': self.get_name(soup_page),
            'address': self.get_address(soup_page),
            'phone': self.get_phone(soup_page),
            'website': self.get_website(soup_page),
            'position': self.get_position(soup_page),
        }

    @staticmethod
    def get_name(soup_page):
        return soup_page.find('div', id="office-details").h2.text

    @staticmethod
    def get_address(soup_page):
        return soup_page.find('div', id="office-details").li.text

    @staticmethod
    def get_phone(soup_page):
        phone_pattern = re.compile("Phone:([ 0-9]+)")
        result = soup_page.find('li', text=phone_pattern).text
        return re.match(phone_pattern, result).groups()[0].strip()

    @staticmethod
    def get_website(soup_page):
        return soup_page.find('a', text="View our website").get('href')

    @staticmethod
    def get_position(soup_page):
        pos_pattern = re.compile(
            r"position: new google.maps.LatLng\((-?[\.\d]+), (-?[\.\d]+)\)"
            )
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
            listing_ids.extend(self.get_listing_ids_from_soup(soup_page))
            if self.is_last_page(soup_page):
                break
            page_number += 1

        return listing_ids

    def get_listing_ids_from_soup(self, soup_page):
        # Extracts and returns all of the Listing IDs from a single soup page.
        listing_ids = []

        for listing_element in soup_page.find_all(
            'div', {'class': 'listing'}
            ):
            # listing ID is contained in the 'id' tag of the listing div.
            listing_ids.append(self.extract_listing_id(listing_element['id']))
            logging.debug("Listings found: %d" % len(listing_ids))

        return listing_ids

    def get_listings_page_url(self, page_number):
        # The url of the office details page. These are paginated, so we must
        # iterated through the page numbers to retrieve all of the data.
        return (
            "%s%s/page%d"
            % (self.__class__.BASE_URL, self.office_id, page_number)
            )

    @staticmethod
    def is_last_page(soup_page):
        # checks for a "Next Page" link
        return not soup_page.find('a', text='Next Page')

    @staticmethod
    def extract_listing_id(text):
        # Get the numerical part of the listing ID only
        return re.search(r"\d+", text).group()


class Listing(WebModel):

    BASE_URL = "http://www.realestate.co.nz/"

    def __init__(self, listing_id, throttle_delay=5, test_listing_html=None):
        ''' Note: listing_html can be explicitly supplied for testing
        purposes only'''
        WebModel.__init__(self, throttle_delay)
        self.listing_id = listing_id
        if test_listing_html:
            self.html_page = test_listing_html
        else:
            self.html_page = self.fetch_html_page(self.reinz_url)
        self.soup_page = BeautifulSoup(self.html_page)

    def get_listing_details(self):
        ''' Collect all of the listing details into a dictionary '''
        listing_details = {}
        attributes = (
            'listing_id',
            'title',
            'description',
            'price',
            'agent_id',
            'address',
            'agency_url',
            'reinz_url',
            'photo_urls'
            )
        for attr in attributes:
            listing_details[attr] = getattr(self, attr)

        return listing_details

    @property
    def title(self):
        return self._header_details().find('h1').text

    @property
    def price(self):
        return self._header_details().find('h3').contents[0].strip()

    def _header_details(self):
        return self.soup_page.find('div', {'class': 'headerDetails'})

    @property
    def address(self):
        ''' returns a list '''
        breadcrumbs = self.soup_page.find(id='breadcrumbs')
        return [
            a.text
            for a
            in breadcrumbs.find_all('a')[1:]
            ]

    @property
    def description(self):
        return self.soup_page.find(
            'div', {'class': 'description detailsPage'}
            ).p.text

    @property
    def agent_id(self):
        return re.search(
            r'(\d+$)', self._agent_details().a['class'][0]
            ).group()

    def _agent_details(self):
        return self.soup_page.find(
            'div', {'class': 'agentDetailsBox'}
            )

    @property
    def agency_url(self):
        ''' The url of this listing on the agency's own website '''
        return self.soup_page.find(
            'span', {'class': 'viewMoreDetails'}
            ).a['href']

    @property
    def reinz_url(self):
        ''' The url of the listing detail page. '''
        return "%s%s" % (self.__class__.BASE_URL, self.listing_id)

    @property
    def photo_urls(self):
        ''' Photos of this property '''
        pattern = re.compile(r'\["(.+\.jpg)"\]')
        return re.findall(pattern, self.html_page)





class WebModelTest(unittest.TestCase):

    def setUp(self):
        self.web_model = WebModel()
        self.test_url = "http://www.google.com"
        self.expected_content = "<!doctype html>"

    def test_defaults(self):
        self.assertEquals(self.web_model.throttle_delay, 5)

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
            "name":(
                "Double Winkel Real Estate Ltd (Licensed: REAA 2008)"
                " - Professionals, Paremata"
                ),
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
        test_html = file(
            os.path.join(TEST_HTML_FOLDER, "office_page1_test.html")
            ).read()
        self.test_soup_page1 = BeautifulSoup(test_html)
        # test page 2 of 2
        test_html = file(
            os.path.join(TEST_HTML_FOLDER, "office_page2_test.html")
            ).read()
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
        found_listings = self.office.get_listing_ids_from_soup(
            self.test_soup_page2
            )
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

            
class ListingTest(unittest.TestCase):
    '''listing_page_test.html'''

    def setUp(self):
        # test listing object
        logging.debug("entering ListingTest setup")
        test_html = file(
            os.path.join(TEST_HTML_FOLDER, "listing_page_test.html")
            ).read()
        self.listing = Listing('1669912', test_listing_html=test_html)

        self.expected_listing_details = {
            'listing_id': '1669912',
            'title': 'Superb First Home or Investment',
            'description': (
                'This sunny, low maintenance three bedroom home on an '
                'easy-care fenced site is a great start to the property '
                'ladder. With open plan living, bathroom with separate '
                'shower, separate toilet, separate laundry, double lockup '
                'garage and off street parking, this property is a must to '
                'view. Recently refurbished with new carpets, new curtains '
                'and the interior and exterior repainted, there is nothing '
                'to do but move in and enjoy. Being close to shops and '
                'schools, bus routes, Windermere Polytechnic and Greerton '
                'makes this an ideal first home or investment property. '
                'Rental return $300 - $320 per week. Phone me today '
                'for your personal viewing.'
                ),
            'price': 'Auction',
            'agent_id': '4399',
            'address': [
                'Bay of Plenty',
                'Western Bay Of Plenty',
                'Ohauiti',
                '5B Lawson Place',
                ],
            'agency_url': 'http://www.eves.co.nz/EGT1635e',
            'reinz_url': 'http://www.realestate.co.nz/1669912',
            'photo_urls': [
                "http://images16.realestate.co.nz/listings/1669912/ec03876afd913de159224dc80e581f49.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/f9eb2f728f0da19bdf3095051de13a15.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/6d3187ce1af59e62858852253d307987.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/9987178d56473dc44fbe9c8ef9d9d9bc.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/1212723a8d9a5354fdf9129d04115e94.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/e0cb946ccbb3494d12e62f6b473ccd21.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/47568f6a8efb29ea5d04ad70e6311968.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/eb39332e022fbfe53668723df55441c3.scale.1024x682.jpg",
                "http://images16.realestate.co.nz/listings/1669912/0f05b2e44de9e55958e5948a5aaaa58a.scale.1024x682.jpg",
                ],
        }

    def test_get_listing_details(self):
        self.assertEqual(
            self.listing.get_listing_details(),
            self.expected_listing_details
            )

    def test_listing_id(self):
        self.assertEqual(
            self.listing.listing_id,
            self.expected_listing_details['listing_id']
            )

    def test_title(self):
        self.assertEqual(
            self.listing.title,
            self.expected_listing_details['title']
            )

    def test_description(self):
        self.assertEqual(
            self.listing.description,
            self.expected_listing_details['description']
            )

    def test_price(self):
        self.assertEqual(
            self.listing.price,
            self.expected_listing_details['price']
            )

    def test_agent_id(self):
        self.assertEqual(
            self.listing.agent_id,
            self.expected_listing_details['agent_id']
            )

    def test_address(self):
        self.assertEqual(
            self.listing.address,
            self.expected_listing_details['address']
            )

    def test_agency_url(self):
        self.assertEqual(
            self.listing.agency_url,
            self.expected_listing_details['agency_url']
            )

    def test_reinz_url(self):
        self.assertEqual(
            self.listing.reinz_url,
            self.expected_listing_details['reinz_url']
            )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
        )
    unittest.main()
