import pprint

import rescraper

offices = {"Porirua": "3521",
           "Paremata": "3551",
           "Tawa": "3534",
           "Whitby": "3541",
           "Otaki": "1756",
           "Waikanae": "1703",
           "Paraparaumu": "1663",
           }

def main():
    o = rescraper.Office(offices["Porirua"])
    print "Office: %s" % o.office_id
    pprint.pprint(o.get_office_details())
    print

    print "Listing IDs for this office:"
    o.get_listing_ids()
    listing_ids = o.get_listing_ids()
    pprint.pprint(listing_ids)
    print

    print "Details of those listings:"
    for listing_id in listing_ids:
      print "Listing: %s" % listing_id
      listing = rescraper.Listing(listing_id)
      pprint.pprint(listing.get_listing_detail())

if __name__ == '__main__':
  main()