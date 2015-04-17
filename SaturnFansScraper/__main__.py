__author__ = 'Robert Cope'

import logging
from logging.handlers import RotatingFileHandler

try:
    from config import ScraperConfig
except ImportError:
    from default_config import ScraperConfig

root_logger = logging.getLogger('')
ch = logging.StreamHandler()
formatter = logging.Formatter(ScraperConfig.LOG_FORMAT_STR)
ch.setFormatter(formatter)
root_logger.addHandler(ch)
root_logger.setLevel(logging.INFO)
ch.setLevel(logging.INFO)

from scraper_argparse import argument_parser
from archiver_main import Archiver

arguments = argument_parser.parse_args()

if arguments.log_file:
    fh = RotatingFileHandler(arguments.log_file, maxBytes=3145728, backupCount=3)
    fh.setLevel(ScraperConfig.LOG_FILE_LOG_LEVEL)
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)

archiver = Archiver(arguments.base_url, arguments.forum_codes, arguments.archive_location,  ScraperConfig.USER_AGENT)

try:
    if archiver.setup():
        archiver.run()
except KeyboardInterrupt:
    archiver.shutdown_event.set()

except Exception as e:
    raise e
finally:
    archiver.teardown()