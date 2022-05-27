from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
        StaleElementReferenceException,
        NoSuchElementException
        )

import dateparser
import urllib
import datetime
import logging
import itertools
import re

import time
from core import DevEntry
import util
from util import cache_result

# When scanning an AAR, if we don't see a post for this long assume it's done
TIMEOUT_DURATION = datetime.timedelta(minutes=120)
# When scanning an AAR, if we don't see a post for this many other posts assume
# it's done
SKIP_THRESHOLD = 350
# Opening sentance to identify AAR list pin (Thanks pelly!)
AARS_TO_DATE_TEXT = "List of AARs to date"

logging.basicConfig()
log = logging.getLogger('discord')

log.level = logging.INFO

def grab_all():
    driver = _login_discord()

    time.sleep(5)

    results = []

    results.extend(_process_official_aars(driver))
    results.extend(_find_unoffical_aars(driver))


    return results

def _find_unoffical_aars(driver):
    log.info("Finding unofficial AARs")
    pins_list = _get_channel_pins(driver, "v3-general")
    log.info("Searching for pelly's AAR index")
    all_pins = pins_list.find_elements(By.CSS_SELECTOR, 'div[class*="messageGroupWrapper-"]')
    pelly_pin = None
    for pin in all_pins:
        if AARS_TO_DATE_TEXT in pin.text:
            pelly_pin = pin
    if pelly_pin is None:
        raise Exception("Missing pelly pin!")
    log.info("Parsing AAR index")
    # find the content div of it
    pp_content = pelly_pin.find_element(By.CSS_SELECTOR, 'div[class*="messageContent-"]')

    ppc_text = pp_content.text
    # parse from top to bottom
    ppc_lines = ppc_text.split('\n')

    results = []
    major_dd_name = None
    minor_dd_name = None
    for line in ppc_lines:
        if line.strip() == "" or AARS_TO_DATE_TEXT in line:
            major_dd_name = None
            minor_dd_name = None
        elif "https://" in line:
            url = line.strip()
            if not url.startswith('https://'):
                loc = line.find('https://')
                minor_dd_name = line[:loc].strip()
                url = line[loc:].strip()
            results.append((major_dd_name, minor_dd_name, url))
        elif major_dd_name == None:
            major_dd_name = line.strip()
            minor_dd_name = line.strip()
        else:
            minor_dd_name = line.strip()

    # This puts things in the "correct" order
    rolists = []
    cur_rolist = None
    prev_maj = None
    for r in results:
        if prev_maj == r[0]:
            cur_rolist.append(r)
        else:
            cur_rolist = [r]
            rolists.append(cur_rolist)
        prev_maj = r[0]
    rolists.reverse()
    results_ordered = itertools.chain(*rolists)

    for majo, mino, url in results_ordered:
        # we need to go back to the pins list and click() it instead of
        # following the url directly! Gross I know!
        if "(edited)" in url:
            url = url.replace('(edited)', '').strip()
        pins_list = _get_channel_pins(driver, "v3-general")
        pin_link = pins_list.find_element(By.CSS_SELECTOR, f'a[href="{url}"]')
        pin_link.click()

        # close the pins dailog so we can see waht's going on!
        pins_button = driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Pinned Messages"]')
        pins_button.click()

        name = f"{majo} - {mino}"
        aar, author, date = _scrape_aar(url, name, driver)
        yield DiscordDevPost(aar, author, name, date)


def _process_official_aars(driver):
    num_done = 0
    results = []
    while True:
        pins_list = _get_channel_pins(driver, "v3-official-aars")
        all_pins = pins_list.find_elements(By.CSS_SELECTOR, 'div[class*="messageGroupWrapper-"]')
        if num_done >= len(all_pins):
            log.info("Done collecting official AARs")
            break
        results = []
        for i, pin in enumerate(all_pins):
            webdriver.ActionChains(driver).move_to_element(pin).perform()
            time.sleep(1)
            if i >= num_done:
                num_done += 1
                title = f"V3 OFFICIAL AAR #{i+1}"
                button = pins_list.find_element(By.CSS_SELECTOR, 'div[class*="jumpButton-"]')
                button.click()
                time.sleep(3)
                url = driver.current_url
                aar, author, date = _scrape_aar(url, title, driver)
                results.append(DiscordDevPost(aar, author, title, date))
    return results


def _get_channel_pins(driver, channel_name):
    # first goto channel
    log.info(f"Searching for #{channel_name} channel")
    channels = driver.find_element(By.CSS_SELECTOR, 'div[id="channels"]')
    c_gen = channels.find_element(By.CSS_SELECTOR, f'li[data-dnd-name="{channel_name}"]')
    c_link = c_gen.find_element(By.TAG_NAME, 'a')
    c_link.click()
    time.sleep(2)
    # then go to pins
    log.info("Searching for pins button")
    pins_button = driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Pinned Messages"]')
    pins_button.click()
    time.sleep(2)
    # find pins list to return
    pins_list = driver.find_element(By.CSS_SELECTOR, 'div[data-list-id="pins"]')
    return pins_list


@cache_result
def _scrape_aar(url, aar_name, driver):
    """Scrape an AAR

    Gets all posts by an author, starting framed by a URL link and gives them
    aar_name
    """
    log.info(f"Scraping AAR: {aar_name}")
    starting_post_id = url.split('/')[-1]
    time.sleep(3)


    all_posts = []
    post_ids = []
    pg = {
            'author': None,
            'date': None,
            'last_date': None,
            'num_skipped': 0
            }

    def add_posts():
        posts = driver.find_elements(By.CSS_SELECTOR, 'li[class*="messageListItem-"]')
        for post in posts:
            try: 
                elem_id = post.get_attribute('id')
                elem_id_number = re.search('[0-9]+', elem_id).group(0)
                if int(elem_id_number) < int(starting_post_id):
                    continue
                if elem_id not in post_ids:
                    post_ids.append(elem_id)
                    author, date, m_id = _get_post_metadata(post)

                    if pg['author'] is not None and pg['author'] != author:
                        # Post by another user, skip it and check
                        if date - pg['last_date'] > TIMEOUT_DURATION:
                            log.info("Ending reading AAR due to timeout")
                            return False
                        pg['num_skipped'] = pg['num_skipped'] + 1
                        if pg['num_skipped'] > SKIP_THRESHOLD:
                            log.info("Ending reading AAR due to postcount-out")
                            return False
                        continue

                    content = _parse_post(post, f"discord-{aar_name}")

                    pg['num_skipped'] = 0
                    if pg['author'] is None:
                        pg['author'] = author
                    if pg['date'] is None:
                        pg['date'] = date
                    pg['last_date'] = date
                    all_posts.append(content)
            except StaleElementReferenceException:
                # The item we wanted to scan got cleaned up too fast!
                continue

        if "You're viewing older messages" not in driver.page_source:
            log.info("Ending reading AAR due to end of channel")
            return False  # we ar at endo of channel

        # Looks like there is more to process
        return True


    sc = driver.find_element(By.CSS_SELECTOR, 'div[class*="scroller-"]')
    has_more = True
    while has_more:
        has_more = add_posts()
        log.debug("Reading posts")
        for _ in range(6):
            sc.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.15)

    all_text = "\n\n".join(all_posts)
    return all_text, pg['author'], pg['date']
    return DiscordDevPost(all_text, pg['author'], aar_name, pg['date'])


_users_cache = {}


def _get_post_metadata(post):
    user_name = None
    try:
        header = post.find_element(By.CSS_SELECTOR, 'span[class*="headerText-"]')
        user_id = header.get_attribute('id')
        user_name = header.text.strip()
        _users_cache[user_id] = user_name
    except NoSuchElementException:
        pass

    if user_name is None:
        message = post.find_element(By.CSS_SELECTOR, 'div[class*="message-"][role="article"]')
        labeled_by = message.get_attribute('aria-labelledby').split(' ')
        message_author = None
        for l in labeled_by:
            if l in _users_cache:
                message_author = _users_cache[l]
    else:
        message_author = user_name

    msg_id = post.get_attribute('id').replace('chat-messages-', '')
    date = dateparser.parse(post.find_element(By.TAG_NAME, 'time').get_attribute('datetime'))

    return message_author, date, msg_id

def _parse_post(post, name):
    result = []

    try:
        reply_ctx = post.find_element(By.CSS_SELECTOR, 'div[class*="repliedMessage-"]')
        reply_user = reply_ctx.find_element(By.CSS_SELECTOR, 'span[class*="username-"]')
        reply_pvw = reply_ctx.find_element(By.CSS_SELECTOR, 'div[class*="repliedTextPreview-"]')
        reply_content = reply_pvw.find_element(By.CSS_SELECTOR, 'div[id*="message-content-"]')

        result.append(f"> **{reply_user.text.strip()}**")
        result.append(f"> {reply_content.text.strip()}")
    except NoSuchElementException as e:
        pass  # Standardized method of failign through

    contents = post.find_element(By.CSS_SELECTOR, 'div[class*="contents-"]')
    content = contents.find_element(By.CSS_SELECTOR, 'div[class*="messageContent-"]')
    content = content.text.strip()
    result.append(content)


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

    return "\n\n".join(result)


def _login_discord():
    driver = _get_selenium()
    driver.get("https://discord.com/channels/831406775416782868/963944118625644605")
    try:
        while "We're so excited to see you again!" in driver.page_source:
            time.sleep(1)
            log.info("Waiting for discord login, CTRL+C to abort")
    except KeyboardInterrupt:
        log.warn("Aborting!")
        return None
    log.info("Sucessful login detected!")
    return driver


def _get_selenium():
    # ff_opts = webdriver.FirefoxOptions()
    # driver = webdriver.Remote(
    #         command_executor="http://172.17.0.1:4444",
    #         options=ff_opts
    #         )
    # return driver
    return webdriver.Firefox()



class DiscordDevPost(DevEntry):
    def __init__(self, body_md, author, source, date):
        self.body_md = body_md
        self.author = author
        self.source = source
        if isinstance(date, str):
            date = dateparser.parse(date)
        self.date = date

    def as_markdown(self):
        return f"""####AAR : {self.source} by {self.author}\n\n""" + self.body_md
