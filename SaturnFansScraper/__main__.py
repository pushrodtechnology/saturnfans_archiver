__author__ = 'Robert Cope'

try:
    from config import ScraperConfig
except ImportError:
    from default_config import ScraperConfig
from scraper_argparse import argument_parser
from archiver_main import Archiver

arguments = argument_parser.parse_args()

archiver = Archiver(arguments.base_url, arguments.forum_codes, arguments.archive_location,  ScraperConfig.USER_AGENT)

try:
    if archiver.setup():
        archiver.run()
except Exception as e:
    raise e
finally:
    archiver.teardown()