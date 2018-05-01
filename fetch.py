import requests
import urllib.parse
import os.path
import shutil
import sys
from typing import List, Tuple, Mapping
from bs4 import BeautifulSoup

sys.setrecursionlimit(1500) # bs4 needs this :-(

UrlToFile = Tuple[str, str]

 # TODO(morrita): Ensure existence.
FETCH_DIR='./f'
PLACE_DIR='./p'

INDEX_URL='https://research.swtch.com/'

def fetch_url(url: str) -> str:
    basename = urllib.parse.quote(url, safe='').replace('%', '_')
    filename = os.path.join(FETCH_DIR, basename)
    if not os.path.isfile(filename):
        print("Requesting: " + url)
        r: requests.Response = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(r.content)
            f.close()
    return filename


def fetch_resources(base: str, text: str) -> List[UrlToFile]:
    page = BeautifulSoup(text, 'html.parser')
    imgs = page.find_all('img')
    srcs = [urllib.parse.urljoin(base, i.get('src')) for i in imgs]    
    return [(s, fetch_url(s)) for s in srcs]


def fetch_index() -> List[str]:
    filename = fetch_url(INDEX_URL)
    soup = BeautifulSoup(open(filename).read(), 'html.parser')
    links = soup.select('ul.toc li a')
    return [ a.get('href') for a in links][1:-1]


def fetch_all() -> UrlToFile:
    links = fetch_index()
    urls = [urllib.parse.urljoin(INDEX_URL, l) for l in links]
    pages : UrlToFile = [(u, fetch_url(u)) for u in urls] 
    for u, p in pages:
        fetch_resources(u, open(p))
    return pages


def make_sure(dirname):
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

TEMPLATE = """
<html>
<head>
  <meta charset="UTF-8">
  <title>{0}</title>
</head>
<body>
{1}
</body>
</html>
"""

def format(text: str):
    page = BeautifulSoup(text, 'html.parser')
    main = page.select('.main')
    title = str(page.head.title.string).replace("research!rsc: ", "")
    return TEMPLATE.format(title, str(main))


def relink(dest: str, pageurl: str, text: str):
    page = BeautifulSoup(text, 'html.parser')
    for i in page.find_all('img'):
        s = fetch_url(urllib.parse.urljoin(pageurl, i.get('src')))
        b = os.path.basename(s)
        d = os.path.join(dest, b)
        i['src'] = b
        shutil.copyfile(s, d)   # Yay side-effect!
    for a in page.find_all('a'):
        href = a.get('href')
        if not urllib.parse.urlsplit(href).scheme:
            a['href'] = urllib.parse.urljoin(pageurl, href)
    return str(page)


def place(dest: str, nch: int, page: UrlToFile) -> str:
    make_sure(dest)
    url = page[0]
    src = fetch_url(url)
    text = open(src).read()
    text = format(text)
    text = relink(dest, url, text)
    filename = os.path.join(dest, 'chapter{:0>3}.html'.format(nch))
    open(filename, 'w').write(text)
    return filename

def drop_placed_dir(path):
    comps = os.path.split(path)
    return os.path.join(*[i for i in comps if i != PLACE_DIR])

if __name__ == "__main__":
    print("Fetching...")
    make_sure(FETCH_DIR)
    pages: List[UrlToFile] = reversed(fetch_all())
    print("Copying...")
    make_sure(PLACE_DIR)
    copied_pages = [ place(PLACE_DIR, i, p) for i, p in enumerate(pages) ]
    TITLE_TEXT = 'title.txt'
    placed_title = os.path.join(PLACE_DIR, TITLE_TEXT)
    shutil.copy(TITLE_TEXT, placed_title)

    cmd = ['pandoc', '-o', 'rsc.epub', placed_title] + copied_pages
    cmd = [drop_placed_dir(c) for c in cmd]
    print(" ".join(cmd))