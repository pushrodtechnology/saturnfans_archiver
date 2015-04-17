__author__ = 'Robert Cope'

from reppy.cache import RobotsCache
import requests


class Archiver(object):
    def __init__(self, base_url, forum_codes, archive_location, user_agent):
        self.base_url = base_url
        self.forum_codes = forum_codes
        self.archive_location = archive_location
        self.user_agent = user_agent
        self.robot_parser = RobotsCache()

    def setup(self):
        self.robot_parser.allowed(self.base_url, self.user_agent)
        return True

    def run(self):
        return True

    def teardown(self):
        return True