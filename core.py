from markdownify import markdownify
from bs4 import BeautifulSoup

class DevEntry(object):
    def as_markdown(self):
        return ""

    def grab_index():
        index_text = get_page_cached(FORUMS_BASE + DD_INDEX)
        dd_re = re.compile(
                "https://forum.paradoxplaza.com/forum/developer-diary/[^/]+/")
        matches = re.findall(dd_re, index_text)

        return matches


class GameScreenshot(object):
    def __init__(self, caption, image_file_path):
        pass

    @staticmethod
    def from_web_url(web_url):
        pass


    @property
    def url(self):
        pass

    @property
    def caption(self):
        pass

    @property
    def ocr_text_searchable(self):
        pass


class Grabber(object):
    def grab_all(self):
        index = self.grab_index
        results = []
        for target_id in index:
            results.append(self.grab_single(target_id))

    def grab_single(self, target_id):
        pass

    def grab_index(self):
        pass

