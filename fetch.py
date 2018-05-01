import requests
import urllib.parse
import os.path
import shutil
import sys
import subprocess
from typing import List, Tuple, Mapping
from bs4 import BeautifulSoup

sys.setrecursionlimit(1500) # bs4 needs this :-(

UrlToFile = Tuple[str, str]

 # TODO(morrita): Ensure existence.
FETCH_DIR='./f'
PLACE_DIR='./p'

TITLE_TEXT = 'metadata.txt'
COVER = 'cover.jpeg'
HTML = 'chapters.html'
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
  <title>research!rsc</title>
</head>
<body>
<h1>About This EPUB File</h1>
<p>This EPUB packages Russ Cox's <href='https://research.swtch.com/'>great blog articles</a> for offline reading.
This file is not affiliated with Russ Cox himself. So please don't contact him about the EPUB packaging and 
formatting problems. This is provided best-effort basis from one of his fans.</p>
<p>The original articles are licensed under a <a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Lisence</a>.</p>
{0}
</body>
</html>
"""

def format(text: str):
    page = BeautifulSoup(text, 'html.parser')
    main = page.select('.main')
    title = str(page.head.title.string).replace("research!rsc: ", "")
    return TEMPLATE.format(title, str(main))


def relink(dest: str, pageurl: str, text: str) -> BeautifulSoup:
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
    return page


def drop_placed_dir(path):
    comps = os.path.split(path)
    return os.path.join(*[i for i in comps if i != PLACE_DIR])


if __name__ == "__main__":
    print("Fetching...")
    make_sure(FETCH_DIR)
    pages: List[UrlToFile] = reversed(fetch_all())
    print("Copying...")
    make_sure(PLACE_DIR)
    soups = [ relink(PLACE_DIR, p[0], open(p[1]).read()) for p in pages ]

    root = BeautifulSoup(features='html.parser')
    for s in soups:
        root.append(s.select(".article")[0])
    for i in root.select(".article"):
        i.unwrap()
    
    htmltext = TEMPLATE.format(str(root))
    placed_html = os.path.join(PLACE_DIR, HTML)
    open(placed_html, 'w').write(htmltext)
    placed_title = os.path.join(PLACE_DIR, TITLE_TEXT)
    shutil.copy(TITLE_TEXT, placed_title)
    placed_cover = os.path.join(PLACE_DIR, COVER)
    shutil.copy(COVER, placed_cover)

    cmd = ['pandoc', '-o', 'rsc.epub', '--epub-metadata', placed_title, 
           '--epub-cover-image', placed_cover, placed_html]
    cmd = [drop_placed_dir(c) for c in cmd]
    print(" ".join(cmd))
    os.chdir(PLACE_DIR)
    subprocess.call(cmd)