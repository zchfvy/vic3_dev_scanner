import hashlib
import os
import requests
import json
import shutil
import logging
from urllib.parse import urlparse

logging.basicConfig()
log = logging.getLogger('util')

log.level = logging.DEBUG

from appdirs import user_cache_dir
import numpy as np

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

def get_cache_dir(dirname):
    # cache_dir = user_cache_dir("Victoria3_DevDiaryScanner", "zchfvy")
    cache_dir = './.cache'
    cache_dir = os.path.join(cache_dir, dirname)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir


def get_output_dir():
    return './output'


def get_page_cached(url, force_refresh=False):
    if not force_refresh:
        cache_dir = get_cache_dir('web')

        h = hashlib.sha256()
        h.update(url.encode('utf-8'))
        cache_hash = h.hexdigest()
        cache_file = os.path.join(cache_dir, cache_hash)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return f.read()

    web = requests.get(url)
    text = web.text

    with open(cache_file, 'w') as f:
        f.write(text)
    return text


def cache_result(func):
    def wrapped(*args, **kwargs):
        h = hashlib.sha256()
        h.update(args[0].encode('utf-8'))
        cache_hash = h.hexdigest()

        cache_dir = get_cache_dir(os.path.join('funcs', func.__name__))
        cached_results = os.path.join(cache_dir, cache_hash)
        if os.path.exists(cached_results):
            with open(cached_results, 'r') as f:
                return json.load(f)
        res = func(*args, **kwargs)
        with open(cached_results, 'w') as f:
            json.dump(res, f, cls=NpEncoder)
        return res
    return wrapped


import easyocr
reader = easyocr.Reader(['en']) # this needs to run only once to load the model into memory

@cache_result
def _ocr_image(path):
    log.debug(f"Running OCR on image {path}")
    result = reader.readtext(path)
    return result

def ocr_image(path):
    data = _ocr_image(path)
    res = []
    for i in data:
        bounds = i[0]
        text = i[1]
        confidence = i[2]
        res.append(text)
    return ' '.join(res)

def download_image(url, subdir_name):
    """Safely put a web image into a local directory and return it's path.
    """
    dest_dir = os.path.join(get_output_dir(), "images", subdir_name)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    im_name = os.path.basename(urlparse(url).path)
    im_path = os.path.join(dest_dir, im_name)
    if not os.path.exists(im_path):
        log.debug(f"Downloading image {url}")
        im_data = requests.get(url, stream=True)
        if im_data.status_code != 200:
            del im_data
            return None, None, ""
        with open(im_path, 'wb') as of:
            shutil.copyfileobj(im_data.raw, of)
        del im_data
    src = os.path.join("images", subdir_name, im_name)
    thumb_src = make_thumbnail(subdir_name, im_name)
    if im_path.endswith(".gif"):
        ocr = "CANNOT OCR AN ANIMATED GIF"
    else:
        ocr = ocr_image(im_path)
    return src, thumb_src, ocr


def make_thumbnail(subdir_name, im_name):
    dest_dir = os.path.join(get_output_dir(), "thumbs", subdir_name)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    src_img = os.path.join(get_output_dir(), "images", subdir_name, im_name)
    dst_img = os.path.join(get_output_dir(), "thumbs", subdir_name, im_name)
    if os.path.exists(dst_img):
        return os.path.join("thumbs", subdir_name, im_name)
    log.debug(f"Generating thumbnail {dst_img}")
    os.popen(f"convert '{src_img}' -resize 100x\> '{dst_img}'")
    return os.path.join("thumbs", subdir_name, im_name)
