__author__ = 'Robert Cope'


class ScraperConfig(object):
    BASE_URL = 'http://www.saturnfans.com/'
    FORUM_CODES = [79, 39, 58]  # These are S-Series General, S-Series Tech, and S-Series Mods, respectively.
    ARCHIVE_SUBURL = '/forums/archive/index.php/f-{forum_code}.html'  # Sub-url for accessing archive mode posts.