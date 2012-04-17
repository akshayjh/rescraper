import urllib2
from bs4 import BeautifulSoup
import re


offices = {"Porirua": "3521",
		   "Paremata": "3551",
		   "Tawa": "3534",
		   "Whitby": "3541",
		   "Otaki": "1756",
		   "Waikanae": "1703",
		   "Paraparaumu": "1663",
		   }

def main():
	OfficeDetailPage("1663").get_listing_ids()

class OfficeDetailPage(object):

	BASE_URL = "http://www.realestate.co.nz/profile/office/"

	def __init__(self, office_id):
		self.office_id = office_id

	def get_listing_ids(self):

		listing_ids = []

		self.get_first_page()

		while self.not_last_page():
			print "page %d" % self.page_no
			for listing_element in self.soup.find_all('div', {'class': 'listing'}):
				# listing ID is contained in the 'id' tag of the listing div.
				listing_ids.append(self.extract_listing_id(listing_element['id']))
			print "listings found: %d" % len(listing_ids)
			self.get_next_page()

		return listing_ids

	def get_first_page(self):
		self.page_no = 1
		self.make_soup()

	def get_next_page(self):
		self.page_no += 1
		self.make_soup()

	def make_soup(self):
		# Make a soup object from the current page of the Office details
		self.soup = BeautifulSoup(self.fetch_html_page())

	def fetch_html_page(self):
		# fetch html page from the web
		return urllib2.urlopen(self.get_url()).read()

	def get_url(self):
		# The url of the office details page. These are paginated, so we must
		# iterated through the page numbers to retrieve all of the data.
		return "%s%s/page%d" % (self.__class__.BASE_URL, self.office_id, self.page_no)

	def not_last_page(self):
		return self.soup.find('a', text='Next Page')

	def extract_listing_id(self, text):
		# Get the numerical part of the listing ID only
		return re.search(r"\d+", text).group()


if __name__ == '__main__':
	main()