__author__ = 'Robert Cope'

try:
    from config import ScraperConfig
except ImportError:
    from default_config import ScraperConfig

import logging

archiver_logger = logging.getLogger(__name__)
if not archiver_logger.handlers:
    ch = logging.StreamHandler()
    archiver_logger.addHandler(ch)
    archiver_logger.setLevel(logging.INFO)

import threading
import time
import os
from Queue import Queue
# TODO: Get regular expression implementation that releases GIL.
import re
from urlparse import urljoin

from reppy.cache import RobotsCache
import requests


class Archiver(object):
    ARCHIVE_SUBFORUM_SUBURL_TEMPLATE = 'index.php/f-{forum_code}.html'
    ARCHIVE_SUBFORUM_SUBURL_RE_TEMPLATE = 'index.php/f-{forum_code}[^(.html)]?.html'
    ARCHIVE_THREAD_SUBURL_RE = 'index.php/t-[^(.html)]*.html'
    ARCHIVE_CSS_RE = '[^(.css)]*.css'

    def __init__(self, base_url, forum_codes, archive_location, user_agent):
        archiver_logger.info('Archiver initialized.')
        self.base_url = base_url
        self.forum_codes = forum_codes
        self.archive_location = archive_location
        self.user_agent = user_agent
        self.robot_parser = RobotsCache()
        self.shutdown_event = threading.Event()
        self.scraper_timer = None
        self.workers = []
        self.pages_need_visiting = Queue()
        self.pages_visited = Queue()
        self.page_re_filters = []

    def setup(self):
        archiver_logger.info('Beginning Archiver setup.')
        success = True

        archiver_logger.info('Building page filters.')
        # Build regular expression filters for pages to attempt to crawl.
        archive_base_url = urljoin(self.base_url, self.archive_location)

        # Build regular expression for sub-forums we're interested in.
        for forum_code in self.forum_codes:
            regex = urljoin(archive_base_url, self.ARCHIVE_SUBFORUM_SUBURL_RE_TEMPLATE.format(forum_code=forum_code))
            self.page_re_filters.append(re.compile(regex))

        # Add a regular expression for thread pages.
        thread_regex = urljoin(archive_base_url, self.ARCHIVE_THREAD_SUBURL_RE)
        self.page_re_filters.append(re.compile(thread_regex))

        # Finally add a regular expression to grab the archive CSS.
        css_regex = urljoin(archive_base_url, self.ARCHIVE_CSS_RE)
        self.page_re_filters.append(re.compile(css_regex))

        archiver_logger.info('Adding seed pages.')
        for fc in self.forum_codes:
            subforum_url = urljoin(self.archive_location, self.ARCHIVE_SUBFORUM_SUBURL_TEMPLATE.format(forum_code=fc))
            self.pages_need_visiting.put(subforum_url)
            archiver_logger.info('Archiver seeded with page {}.'.format(subforum_url))

        archiver_logger.info('Checking archive location...')
        # Setup archive location.
        base_path, new_archive = os.path.split(self.archive_location)
        if not os.path.exists(base_path) or not os.path.isdir(base_path):
            success = False
            archiver_logger.error('Base path {} does not exist or is not a directory! Aborting!')
            return success
        elif (os.path.exists(self.archive_location) and
                (not os.path.isdir(self.archive_location) or os.listdir(self.archive_location))):
            success = False
            archiver_logger.error('Archive location {} is either a not a directory or is not empty! Aborting!'
                                  ''.format(self.archive_location))
            return success
        elif not os.path.exists(self.archive_location):
            archiver_logger.info('Creating archive directory {}.'.format(self.archive_location))
            try:
                os.mkdir(self.archive_location)
            except OSError:
                success = False
                archiver_logger.exception('Faulted attempting to create archive directory! Aborting!')
                return success
        else:
            archiver_logger.info('Empty archive directory {} exists. Proceeding...'.format(self.archive_location))

        # Attempt to retrieve robots.txt information about target site.
        if not self.robot_parser.allowed(self.base_url, self.user_agent):
            success = False
            archiver_logger.error('Not allowed to scrape {}! Aborting!'.format(self.base_url))
            return success
        else:
            archiver_logger.info('Successfully polled {} for robots.txt, can scrape.'.format(self.base_url))

        # Get crawl delay and build scraper timer.
        delay_time = self.robot_parser.delay(self.base_url, self.user_agent)
        if delay_time:
            archiver_logger.info('Site crawl-delay: {} seconds.'.format(delay_time))

        else:
            delay_time = ScraperConfig.DEFAULT_CRAWL_DELAY
            archiver_logger.info('No crawl delay for this site. Using default crawl delay of {} seconds.'
                                 ''.format(delay_time))
        archiver_logger.info('Intializng Scraper timer.')
        self.scraper_timer = ScraperTimer(delay_time)
        return success

    def run(self):
        return True

    def teardown(self):
        self.shutdown_event.set()
        return True


class ScraperTimer(object):
    def __init__(self, crawl_delay):
        self.crawl_delay = crawl_delay
        self.crawl_times = [0]
        self.crawl_times_lock = threading.Lock()

    def wait(self):
        current_time = time.time()
        latest_call = max(self.crawl_times)
        delta = current_time - latest_call
        if delta > self.crawl_delay:
            with self.crawl_times_lock:
                self.crawl_times.append(current_time)
        else:
            crawl_time = latest_call + self.crawl_delay
            with self.crawl_times_lock:
                self.crawl_times.append(crawl_time)
            time.sleep(crawl_time - time.time())
        self._remove_stale_crawl_times()
        return

    def _remove_stale_crawl_times(self):
        current_time = time.time()
        stale_calls = [t for t in self.crawl_times if current_time - t > self.crawl_delay]
        for stale_call in stale_calls:
            with self.crawl_times_lock:
                self.crawl_times.remove(stale_call)


class ScraperWorker(threading.Thread):
    pass