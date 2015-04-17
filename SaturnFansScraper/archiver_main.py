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

from reppy.cache import RobotsCache
import requests


class Archiver(object):
    def __init__(self, base_url, forum_codes, archive_location, user_agent):
        archiver_logger.info('Archiver initialized.')
        self.base_url = base_url
        self.forum_codes = forum_codes
        self.archive_location = archive_location
        self.user_agent = user_agent
        self.robot_parser = RobotsCache()
        self.shutdown_event = threading.Event()
        self.scraper_timer = None

    def setup(self):
        archiver_logger.info('Beginning Archiver setup.')
        success = True
        if not self.robot_parser.allowed(self.base_url, self.user_agent):
            success = False
            archiver_logger.error('Not allowed to scrape {}! Aborting!'.format(self.base_url))
            return success
        else:
            archiver_logger.info('Successfully polled {} for robots.txt, can scrape.'.format(self.base_url))

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