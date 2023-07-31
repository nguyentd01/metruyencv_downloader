import httpx
from bs4 import *
from ebooklib import epub
import asyncio
import os


def download(url,file_name):
    img_data = httpx.get(url).content
    return img_data


async def get(client, url):
    resp = await client.get(url)
    chapter_content = BeautifulSoup(resp.content, features='lxml')
    html = str(chapter_content.find('div', class_='c-c'))
    chapter_title = str(chapter_content.find('div', class_='h1 mb-4 font-weight-normal nh-read__title'))
    html = html.replace('<div class="pt-3 text-center" style="margin-right: -1rem;"><div class="mb-1 fz-13"><small class="text-muted"><small>— QUẢNG CÁO —</small></small></div><div class="my-1"></div></div>','')
    html = f'<h2>{chapter_title}</h2>' + html
    if 'Vui lòng đăng nhập để đọc tiếp nội dung' in html:
        return None
    else:
        return chapter_title, html

limits = httpx.Limits(max_keepalive_connections=None, max_connections=None,keepalive_expiry=None)
timeout = httpx.Timeout(None)


async def main():
    async with httpx.AsyncClient(timeout=timeout,limits=limits) as client:
        tasks = []
        for number in range(1, max_chapter + 1):
            url = f'{link}/chuong-{number}'
            tasks.append(asyncio.ensure_future(get(client, url)))
        texts = await asyncio.gather(*tasks)
        await asyncio.sleep(1)
        return texts

chapter_links = []
if __name__ == '__main__':
    print('Đây chỉ là bản beta,xin hãy đừng download quá 2000 chapter để tránh tình trạng thiếu chap')
    link = input('metruyencv link:')
    web = httpx.get(link)
    content = web.content
    bs = BeautifulSoup(content, features='lxml')
    max_chapter = int(bs.find('div', class_='font-weight-semibold h4 mb-1').text)
    author = bs.find('a', class_='text-secondary').text
    status = bs.find('li', class_='d-inline-block border border-danger px-3 py-1 text-danger rounded-3 mr-2 mb-2').text
    title = str(bs.find('h1', class_='h3 mr-2').text)
    path = f'D:/novel/{title}'
    filename1 = link.replace('https://metruyencv.com/truyen/','').replace('-','')
    image_url = bs.find('div', class_='nh-thumb nh-thumb--210 shadow').select_one('img').get('src')
    try:
        os.makedirs(path)
    except OSError as error:
        pass
    image = download(image_url, f'{path}/cover.jpg')
    attribute = str(bs.find('li', class_='d-inline-block border border-primary px-3 py-1 text-primary rounded-3 mr-2 mb-2').find('a').text)
    print(filename1)
    print(status)
    print(attribute)
    print(author)
    print(max_chapter)
    print(image_url)
    a = asyncio.run(main())
    a = dict([x for x in a if x is not None])
    if a == {} or a == None:
        print('error')
        quit()
    book = epub.EpubBook()
    book.set_title(title=title)
    book.set_identifier("DuckPenis69")
    book.add_author(author=author)
    book.set_language('vn')
    book.add_metadata(None, 'meta', '', {'name': 'status', 'content': status})
    book.add_metadata(None, 'meta', '', {'name': 'max_chapter', 'content': str(max_chapter)})
    book.set_cover(content=image,file_name='cover.jpg')
    c = 1
    book.add_metadata(None, 'meta', '', {'name': f'attribute', 'content': attribute})
    titles = []
    i = 1
    b = 1
    for chapter_title, html in a.items():
        if b == 1:
            html = f'<h1>{title}</h1>' + html
            b += 1
        chapter_title = BeautifulSoup(chapter_title,features='lxml').text
        html = BeautifulSoup(html, features='lxml')
        titles.append(chapter_title)
        file_name = f'chapter{i}' + '.html'
        globals()['chapter%s' % i] = epub.EpubHtml(lang='vn', title=chapter_title, file_name= file_name,uid=f'chapter{i}')
        globals()['chapter%s' % i].content = str(html)
        print(globals()['chapter%s' % i])
        book.add_item(globals()['chapter%s' % i])
        i += 1
    chapter_names = []
    for a in range(1,i):
        chapter_names.append(f'chapter{a}')
    book.toc = ()
    style = '''
        body {
            font-family: Cambria, Liberation Serif, Bitstream Vera Serif, Georgia, Times, Times New Roman, serif;
        }

        h1 {
             text-align: left;
             text-transform: uppercase;
             font-weight: 400;     
        }
        
        h2 {
             text-align: left;
             text-transform: uppercase;
             font-weight: 300;     
        }
        '''

    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    book.spine = chapter_names
    print(book)
    epub.write_epub(f'{path}/{filename1}.epub', book)
    print('Download successfully. Your epub file is in "D:/novel" folder')
    print('Press enter to exit')
    input()

