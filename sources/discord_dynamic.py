from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
        StaleElementReferenceException,
        NoSuchElementException
        )

import dateparser
import urllib

import time
from core import DevEntry
import util


def grab_all():
    driver = _login_discord()

    results = []

    official_ottoman_aar = _scrape_full_channel(driver,
                               "831406775416782868/963944118625644605",
                               "#v3-official-aars")
    results.extend(official_ottoman_aar)

    return results


def _scrape_full_channel(driver, chan_id, chan_name):
    # Official AAR channel
    driver.get(f"https://discord.com/channels/{chan_id}")
    time.sleep(6)
    sc = driver.find_element(By.CSS_SELECTOR, 'div[class*="scroller-"]')
    w = 0
    maxw = 25
    while f"This is the start of the {chan_name} channel." not in driver.page_source:
        sc.send_keys(Keys.PAGE_UP)
        if w <= 0:
            print("\nScrolling to top of channel", end='')
            w = maxw
        w -= 1
        print('.', end='', flush=True)
        time.sleep(0.25)
    print('\nFound top of channel!')

    all_posts = []
    post_ids = []
    pg = {
            'author': None,
            'date': None
            }

    def add_posts():
        posts = driver.find_elements(By.CSS_SELECTOR, 'li[class*="messageListItem-"]')
        for post in posts:
            try: 
                elem_id = post.get_attribute('id')
                if elem_id not in post_ids:
                    content, author, date, m_id = _parse_post(post, f"discord-{chan_name}")
                    if pg['author'] is None:
                        pg['author'] = author
                    if pg['date'] is None:
                        pg['date'] = date
                    all_posts.append(content)
                    post_ids.append(elem_id)
            except StaleElementReferenceException:
                # The item we wanted to scan got cleaned up too fast!
                continue


    while "You're viewing older messages" in driver.page_source:
        add_posts()
        print("Reading posts")
        for _ in range(4):
            sc.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.15)
    # one more time
    add_posts()

    results = []
        
    all_text = "\n\n".join(all_posts)
    return [DiscordDevPost(all_text, pg['author'], chan_name, pg['date'])]


_users_cache = {}


def _parse_post(post, name):
    result = []

    msg_id = post.get_attribute('id').replace('chat-messages-', '')
    date = dateparser.parse(post.find_element(By.TAG_NAME, 'time').get_attribute('datetime'))
    content = post.find_element(By.CSS_SELECTOR, 'div[class*="messageContent-"]')
    content = content.text.strip()
    result.append(content)

    try:
        header = post.find_element(By.CSS_SELECTOR, 'span[class*="headerText-"]')
        user_id = header.get_attribute('id')
        user_name = header.text.strip()
        _users_cache[user_id] = user_name
    except NoSuchElementException:
        pass  # Standardized method of failign through

    message = post.find_element(By.CSS_SELECTOR, 'div[class*="message-"][role="article"]')
    labeled_by = message.get_attribute('aria-labelledby').split(' ')
    message_author = None
    for l in labeled_by:
        if l in _users_cache:
            message_author = _users_cache[l]

    image_wrapper = post.find_elements(By.CSS_SELECTOR, 'div[class*="imageWrapper-"]')
    for iw in image_wrapper:
        image_url = iw.find_element(By.TAG_NAME, 'a').get_attribute('href')
        src, thumb_src, ocr = util.download_image(image_url, name, uniq_name=True)
        result.append(f"")
        img_tag = f"""![Image]({urllib.parse.quote(thumb_src)})"""
        link_tag = f"""[{img_tag}]({urllib.parse.quote(src)})"""
        ocr_text = f"""<font size=1>OCR: {ocr}</font>"""
        result.append(link_tag)
        result.append(ocr_text)

    return "\n\n".join(result), message_author, date, msg_id


def _login_discord():
    driver = webdriver.Firefox()
    driver.get("https://discord.com/channels/831406775416782868/963944118625644605")
    try:
        while "We're so excited to see you again!" in driver.page_source:
            time.sleep(1)
            print("Waiting for discord login, CTRL+C to abort")
    except KeyboardInterrupt:
        print("Aborting!")
        return None
    print("Sucessful login detected!")
    return driver


class DiscordDevPost(DevEntry):
    def __init__(self, body_md, author, source, date):
        self.body_md = body_md
        self.author = author
        self.source = source
        self.date = date

    def as_markdown(self):
        return f"""####{self.author} posted in {self.source}\n\n""" + self.body_md




if __name__ == '__main__':
    ap = grab_all()
    print(ap)
