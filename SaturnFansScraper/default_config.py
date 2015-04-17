__author__ = 'Robert Cope'

import logging


class ScraperConfig(object):
    BASE_URL = 'http://www.saturnfans.com/'
    FORUM_CODES = [79, 39, 58]  # These are S-Series General, S-Series Tech, and S-Series Mods, respectively.
    ARCHIVE_SUBURL = '/forums/archive/'  # Sub-url for accessing archive mode posts.
    USER_AGENT = 'Saturn Fans Scraper v0.0.1'
    ARCHIVE_LOCATION = '/tmp/saturn_fans'
    DEFAULT_CRAWL_DELAY = 0.5
    LOG_FILE = ''  # If not empty, save logs to a file somewhere.
    LOG_FILE_LOG_LEVEL = logging.INFO  # Default log level when logging to a file.
    # Logger format string
    LOG_FORMAT_STR = '[%(asctime)s] -  %(levelname)s - %(message)s - (%(name)s : %(funcName)s : %(lineno)d : ' \
                     'T%(thread)d)'
    DEFAULT_WORKER_COUNT = 2