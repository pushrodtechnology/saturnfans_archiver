__author__ = 'Robert Cope'

try:
    from config import ScraperConfig
except ImportError:
    from default_config import ScraperConfig

import logging

import threading
import time
import os
from Queue import Queue
# TODO: Get regular expression implementation that releases GIL.
import re
from urlparse import urljoin, urlsplit

from reppy.cache import RobotsCache
import requests
from bs4 import BeautifulSoup

archiver_logger = logging.getLogger(__name__)


class Archiver(object):
    ARCHIVE_SUBFORUM_SUBURL_TEMPLATE = 'index.php/f-{forum_code}.html'
    ARCHIVE_SUBFORUM_SUBURL_RE_TEMPLATE = 'index.php/f-{forum_code}[^(.html)]?.html'
    ARCHIVE_THREAD_SUBURL_RE = 'index.php/t-[^(.html)]*.html'
    ARCHIVE_CSS_RE = '[^(.css)]*.css'

    def __init__(self, base_url, forum_codes, archive_location, user_agent, worker_count):
        archiver_logger.info('Archiver initialized.')
        self.base_url = base_url
        self.archive_base_url = urljoin(self.base_url, ScraperConfig.ARCHIVE_SUBURL)
        self.forum_codes = forum_codes
        self.archive_location = archive_location
        self.user_agent = user_agent
        self.robot_parser = RobotsCache()
        self.scraper_timer = None
        self.shutdown_event = threading.Event()
        self.delay_time = 1

        self.workers = []
        self.worker_count = worker_count

        self.pages_need_visiting = Queue()
        self.pages_need_analysis_counter = RachetingCounter()
        self.pages_visited_lock = threading.Lock()
        self.pages_visited = []
        self.page_re_filters = []

    def setup(self):
        archiver_logger.info('Beginning Archiver setup.')
        success = True

        archiver_logger.info('Building page filters.')
        # Build regular expression filters for pages to attempt to crawl.
        archive_base_url = self.archive_base_url

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
            subforum_url = urljoin(self.archive_base_url, self.ARCHIVE_SUBFORUM_SUBURL_TEMPLATE.format(forum_code=fc))
            self.pages_need_visiting.put(subforum_url)
            self.pages_need_analysis_counter.increment()
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
        self.delay_time = delay_time
        if success:
            archiver_logger.info('Archiver setup success!')
        else:
            archiver_logger.error('Archiver setup failure! Check logs!')
        archiver_logger.info('Building workers...')
        for i in xrange(self.worker_count):
            archiver_logger.info('Adding worker {}.'.format(i+1))
            worker = ArchiverWorker(self.shutdown_event, self.user_agent, self.robot_parser, self.scraper_timer,
                                    self.pages_need_visiting, self.pages_visited, self.pages_visited_lock,
                                    self.page_re_filters, self.pages_need_analysis_counter, self.archive_location)
            worker.daemon = True
            self.workers.append(worker)
        return success

    def run(self):
        archiver_logger.info('Starting workers...')
        [worker.start() for worker in self.workers]
        while not self.pages_need_analysis_counter.empty():
            time.sleep(0.1)
        archiver_logger.info('Finished archiving all possible pages. Shutting down.')
        archiver_logger.info('Waiting for threads to finish up.')
        self.shutdown_event.set()
        self.scraper_timer.wait()
        return True

    def teardown(self):
        if not self.shutdown_event.is_set():
            self.shutdown_event.set()
        return True


class RachetingCounter(object):
    def __init__(self, value=0):
        self.value = value
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.value += 1

    def decrement(self):
        assert self.value > 0
        with self.lock:
            self.value -= 1

    def empty(self):
        return self.value == 0


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


class ArchiverWorker(threading.Thread):
    def __init__(self, shutdown_event, user_agent, robot_parser, scraper_timer, pages_need_visiting,
                 pages_visited, pages_visited_lock, page_filters, analysis_counter, archive_location,
                 *args, **kwargs):
        self.shutdown_event = shutdown_event
        self.user_agent = user_agent
        self.robot_parser = robot_parser
        self.scraper_timer = scraper_timer
        self.pages_need_visiting = pages_need_visiting
        self.pages_visited = pages_visited
        self.pages_visited_lock = pages_visited_lock
        self.page_filters = page_filters
        self.analysis_counter = analysis_counter
        self.archive_location = archive_location
        threading.Thread.__init__(self, *args, **kwargs)

        self.session = requests.session()
        self.session.headers['User-Agent'] = self.user_agent

    def run(self):
        archiver_logger.info('Worker starting..')
        while not self.shutdown_event.is_set():
            if self.pages_need_visiting.empty():
                time.sleep(0.1)
            else:
                trial_page_url = self.pages_need_visiting.get()
                if (self.robot_parser.allowed(trial_page_url, self.user_agent) and
                        trial_page_url not in self.pages_visited):
                    self.scraper_timer.wait()
                    archiver_logger.info('Retrieving page {}.'.format(trial_page_url))
                    response = self.session.get(trial_page_url)
                    if response.status_code == 200:
                        split_url = urlsplit(response.url, 2)
                        netloc = split_url.netloc
                        asset_path = split_url.path[1:]
                        new_file = os.path.join(self.archive_location, asset_path)
                        new_file_dir, _ = os.path.split(new_file)
                        if not os.path.isdir(new_file_dir):
                            os.makedirs(new_file_dir)
                        for link in self._get_new_links(response.text):
                            self.pages_need_visiting.put(link)
                            self.analysis_counter.increment()
                        with open(new_file, 'w') as f:
                            f.write(self._alter_links(response.content, netloc))
                    with self.pages_visited_lock:
                        self.pages_visited.append(trial_page_url)
                self.analysis_counter.decrement()
                self.pages_need_visiting.task_done()

    def _alter_links(self, data, base_netloc):
        return re.sub('http[s]?://{netloc}'.format(netloc=re.escape(base_netloc)), self.archive_location, data)

    def _get_new_links(self, page_content):
        new_links = []
        page_soup = BeautifulSoup(page_content)
        candidate_links = page_soup.find_all('link', {'href': True}) + page_soup.find_all('a', {'href': True})
        for link in candidate_links:
            href = link.get('href')
            if self._apply_filters(href):
                new_links.append(href)
        return new_links

    def _apply_filters(self, link):
        for page_filter in self.page_filters:
            if page_filter.search(link):
                return True
        return False