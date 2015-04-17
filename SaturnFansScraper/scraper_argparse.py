__author__ = 'Robert Cope'

import argparse

try:
    from config import ScraperConfig
except ImportError:
    from default_config import ScraperConfig


argument_parser = argparse.ArgumentParser(description='SaturnFansScraper Version 0.0.1 (LGPLv2)',
                                          prog='python -m SaturnFansScraper')
argument_parser.add_argument('-url', '--base_url', type=str, nargs='?', default=ScraperConfig.BASE_URL,
                             help='Base of the site to scrape. Default: {}.'.format(ScraperConfig.BASE_URL))
argument_parser.add_argument('-al', '--archive_location', type=str, nargs='?', default=ScraperConfig.ARCHIVE_LOCATION,
                             help='The location to build the Saturn Fans archive in. '
                                  'Default: {}.'.format(ScraperConfig.ARCHIVE_LOCATION))
argument_parser.add_argument('-lf', '--log_file', type=str, nargs='?', default=ScraperConfig.LOG_FILE,
                             help='Location to save log files to. Default: {}.'
                                  ''.format(ScraperConfig.LOG_FILE or '<no log file>'))
argument_parser.add_argument('forum_codes', type=int, nargs='*', default=ScraperConfig.FORUM_CODES,
                             help='The sub-forum numbers to scraper. Defaults: {}.'.format(ScraperConfig.FORUM_CODES))
