import re
import logging
import urllib.parse
import dateparser

from markdownify import markdownify
import bs4
from bs4 import BeautifulSoup

from core import DevEntry, Grabber
import util
from util import get_cache_dir, get_page_cached, cache_result

logging.basicConfig()
log = logging.getLogger('dev_diary')

log.level = logging.INFO

FORUMS_BASE = "https://forum.paradoxplaza.com"
DD_INDEX = "/forum/threads/victoria-3-dev-diary-index.1481698/"
ALL_DEV_POSTS = "/forum/forums/victoria-3.1095/?prdxPsDevPostsOnly=1"

def grab_all():
    index_text = get_page_cached(FORUMS_BASE + DD_INDEX)
    dd_re = re.compile(
            "https://forum.paradoxplaza.com/forum/developer-diary/[^/]+/")
    matches = re.findall(dd_re, index_text)

    results = []
    for m in matches:
        results.extend(grab_batch(m))

    mr_re = re.compile(
            "https://forum.paradoxplaza.com/forum/threads/victoria-3-monthly-update-[^/]+/")
    matches = re.findall(mr_re, index_text)
    for m in matches:
        results.append(grab_monthly(m))


    # Now grab non-DD comments
    # TODO, turen the False to True
    all_dev_posts_url = FORUMS_BASE + ALL_DEV_POSTS
    for i, soup in enumerate(_paginate_through(all_dev_posts_url, False)):
        log.info(f"Capturing dev posts page {i}")
        thread_list = soup.find(class_='js-threadList')
        threads = thread_list.find_all(class_='structItem--thread')
        for thread in threads:
            thread_name = thread.find(class_='structItem-title').get_text().strip()
            thread_url = thread.find(class_='structItem-startDate').find('a').attrs['href']
            location = FORUMS_BASE + thread_url
            # Really bad filtering omg
            if "Dev Diary #" in thread_name:
                continue
            log.info(f"Capturing thread {thread_name} {thread_url}")
            dev_posts = load_dev_posts(location, PdxThread(thread_name, thread_url), False)
            results.extend(dev_posts)


    return results

def grab_batch(url):
    dd_body = get_page_cached(url)
    soup = BeautifulSoup(dd_body, features="html.parser")

    title = str(soup.find('title').get_text().split('|')[0].strip())
    result = []

    log.info(f"Capturing Dev Diary '{title}'")

    u_dt = soup.find_all(class_="u-dt")[0]
    date = dateparser.parse(u_dt.attrs['datetime'])
    bbwrappers = soup.find_all(class_="bbWrapper")
    dd_post = bbwrappers[0]
    contents = dd_post.encode_contents()
    diary = DevDiary(title, contents, url, date)
    dev_posts = load_dev_posts(url, diary, True)

    dev_posts.insert(0, diary)
    return dev_posts


def grab_monthly(url):
    dd_body = get_page_cached(url)
    soup = BeautifulSoup(dd_body, features="html.parser")

    title = str(soup.find('title').get_text().strip())
    result = []

    log.info(f"Capturing Monthly Roundup '{title}'")

    bbwrappers = soup.find_all(class_="bbWrapper")
    mr_post = bbwrappers[0]
    contents = mr_post.encode_contents()
    u_dt = soup.find_all(class_="u-dt")[0]
    date = dateparser.parse(u_dt.attrs['datetime'])

    attachments = soup.find_all(class_="attachmentList")
    for li in attachments[0].find_all('li'):
        im_tag = li.find('img')
        im_src = im_tag.attrs['src']
        full_im_src = re.sub('/thumbnail/', '/', im_src)
        contents = contents + bytes(f"""\n<img src="{full_im_src}" />\n""", 'utf-8')

    return DevMonthlyRoundup(title, contents, url, date)


def load_dev_posts(url, linked_item, dev_diary=True):
    posts_url = url + '?prdxDevPosts=1'

    if dev_diary:
        if linked_item.title == "Dev Diary #43 - The American Civil War":
            ofaloafs_post = _load_single_post_special(28226531)
            return [_parse_post(ofaloafs_post, linked_item, True)]

    for soup in _paginate_through(posts_url):
        messages = soup.find_all('div', class_="message-cell--main")
        result = []
        for post in messages:
            result.append(_parse_post(post, linked_item, dev_diary))

    return result


def _paginate_through(url, force_refresh=False):
    while True:
        if url:
            posts_body = get_page_cached(url, force_refresh)
            soup = BeautifulSoup(posts_body, features="html.parser")
            yield soup
            next_page = soup.find(rel='next')
            if next_page:
                url = FORUMS_BASE + next_page.attrs['href']
            else:
                url = None
        else:
            break


def _load_single_post_special(post_num):
    url = f"https://forum.paradoxplaza.com/forum/goto/post?id={post_num}"
    posts_body = get_page_cached(url)
    soup = BeautifulSoup(posts_body, features="html.parser")
    wrapped = soup.find('article', attrs={"data-content": f"post-{post_num}"}, class_="message-threadStarterPost")
    message = wrapped.find('div', class_="message-cell--main")
    return message


def _parse_post(post, linked_item, dev_diary=True):
    u_dt = post.find_all(class_="u-dt")[0]
    date = dateparser.parse(u_dt.attrs['datetime'])
    post = post.find(class_="message-userContent")
    author = post.attrs['data-lb-caption-desc']
    author = re.sub(r"(\S+)\s.*",
             r"\1",
             post.attrs['data-lb-caption-desc'])
    source = re.sub(r"post-([0-9]+)",
            FORUMS_BASE + r"/forum/goto/post?id=\1",
            post.attrs['data-lb-id'])
    dev_post = post.find(class_='bbWrapper')
    contents = dev_post.encode_contents()
    if dev_diary:
        return DevDiaryComment(linked_item, contents, author, source, date)
    else:
        return NonDiaryDevComment(linked_item, contents, author, source, date)


def standard_substitutions(diary_name, input_text):
    txt = input_text
    # Weird lightbox things in the earlier DDs
    txt = re.sub(r""" {\n( "lightbox\\_.*\n)+ }\n """, "", txt)
    # Substitute links to posts for the full URLs
    txt = re.sub(r"""\((/forum/goto/post\?id=[0-9]+)\)""",
            r"(https://forum.paradoxplaza.com\1)", txt)

    images = re.finditer(r"""!\[([^]]*)\]\(([^"\n]*)( "([^"]*)")?\)""", txt)
    for im in images:
        log.debug("MATCH: " + im.group(0))
        name = im.group(1)
        url = im.group(2)
        alt_text = im.group(4)

        # Don't try to process emojies!
        if re.match(r"""data:image/.*""", url):
            txt = txt.replace(im.group(0), alt_text)
            continue

        # If you link elsewhere on the forum it drops a PDX icon so ignore that
        if re.match(r""".*favicon.ico""", url):
            txt = txt.replace(im.group(0), "")
            continue
        
        src, thumb_src, ocr = util.download_image(url, diary_name)

        if src is None:
            continue  # Guess we can't do anythign if it failed

        img_tag = f"""![{name}]({urllib.parse.quote(thumb_src)} "{alt_text}")"""
        link_tag = f"""[{img_tag}]({urllib.parse.quote(src)})"""
        ocr_text = f"""<font size=1>OCR: {ocr}</font>"""
        txt = txt.replace(im.group(0), link_tag + "\n\n" + ocr_text)

    return txt


class PdxThread(object):
    def __init__(self, title, url):
        self.title = title
        self.url = url

class DevDiary(DevEntry):
    def __init__(self, title, body_html, source, date):
        self.title = title
        self.source = source
        self.body_md = standard_substitutions(self.title, markdownify(body_html))
        self.date = date

    def as_markdown(self):
        return f"#[{self.title}](self.source)\n" + self.body_md


class DevMonthlyRoundup(DevDiary):
    pass  # These are functionally identical to dev diaries


class DevDiaryComment(DevEntry):
    def __init__(self, linked_dd, body_html, author, source, date):
        self.linked_dd = linked_dd
        self.body_md = standard_substitutions(self.linked_dd.title, markdownify(body_html))
        self.body_md = re.sub("Click to expand...", "", self.body_md)
        self.author = author
        self.source = source
        self.date = date

    def as_markdown(self):
        return f"""####[{self.author} reqplied to {self.linked_dd.title}]({self.source})\n""" + self.body_md


class NonDiaryDevComment(DevEntry):
    def __init__(self, thread, body_html, author, source, date):
        self.thread_title = thread.title
        self.thread_url = thread.url
        self.body_md = standard_substitutions(self.thread_title, markdownify(body_html))
        self.body_md = re.sub("Click to expand...", "", self.body_md)
        self.author = author
        self.source = source
        self.date = date

    def as_markdown(self):
        return f"""####[{self.author} commented on {self.thread_title}]({self.source})\n""" + self.body_md
