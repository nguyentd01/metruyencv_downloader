import httpx
from bs4 import *
from ebooklib import epub
import asyncio
import os


def download(url):
    img_data = httpx.get(url).content
    return img_data


async def get(client, url):
    resp = await client.get(url)
    chapter_content = BeautifulSoup(resp.content, features='lxml')
    html = str(chapter_content.find('div', class_='break-words'))
    chapter_title = str(chapter_content.find('h2', class_='text-center text-gray-600 dark:text-gray-400 text-balance').text)
    if 'Vui lòng đăng nhập để đọc tiếp nội dung' in html:
        return None
    else:
        return chapter_title, html


limits = httpx.Limits(max_keepalive_connections=5000, max_connections=10000)
timeout = httpx.Timeout(100)


async def main():
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        tasks = []
        for number in range(1, max_chapter + 1):
            url = f'{link}/chuong-{number}'
            tasks.append(asyncio.ensure_future(get(client, url)))
        texts = await asyncio.gather(*tasks)
        return texts


exit = True
chapter_links = []

if __name__ == '__main__':
    while True:
        print('Đây chỉ là bản beta,xin hãy đừng download quá 1000 chapter để tránh tình trạng thiếu chap')
        if exit:
            a = input('Bạn có muốn thoát ra sau khi tải xong không?(c/k):').lower()
            if a == 'k':
                exit = False
        
        link = input('metruyencv link:')
        max_chapter = int(input('Nhập số chapter bạn muốn tải:'))
        web = httpx.get(link)
        content = web.content
        bs = BeautifulSoup(content, features='lxml')
        author = str(bs.find('a', class_='text-gray-500').text).strip()
        status = str(bs.find('a', class_='inline-flex border border-primary rounded px-2 py-1 text-primary').select_one('span').text).strip()
        title = str(bs.find('h1', class_='mb-2').text)
        path = f"D:/novel/{title.replace(':', ',')}"
        filename1 = link.replace('https://metruyencv.com/truyen/', '').replace('-', '')
        image_url = bs.find('img', class_='w-44 h-60 shadow-lg rounded mx-auto').get('src')
        try:
            os.makedirs(path)
        except OSError as error:
            pass
        image = download(image_url)
        attribute = str(bs.find('a', class_='inline-flex border border-rose-700 dark:border-red-400 rounded px-2 py-1 text-rose-700 dark:text-red-400').text)
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
        titles = []
        i = 1
        b = 1
        for chapter_title, html in a.items():
            html = f'<h2>{chapter_title}</h2>' + html
            if b == 1:
                html = f'<h1>{title}</h1>' + html
                b += 1
            chapter_title = BeautifulSoup(chapter_title, features='lxml').text
            html = BeautifulSoup(html, features='lxml')
            titles.append(chapter_title)
            file_name = f'chapter{i}' + '.html'
            globals()['chapter%s' % i] = epub.EpubHtml(lang='vn', title=chapter_title, file_name=file_name,
                                                       uid=f'chapter{i}')
            globals()['chapter%s' % i].content = str(html)
            print(globals()['chapter%s' % i])
            book.add_item(globals()['chapter%s' % i])
            i += 1

        
        chapter_names = []
        for a in range(1, i):
            chapter_names.append(f'chapter{a}')
        book.set_title(title=title)
        book.set_identifier("DuckPenis69")
        book.add_author(author=author)
        book.set_language('vn')
        book.add_metadata(None, 'meta', '', {'name': 'status', 'content': status})
        book.add_metadata(None, 'meta', '', {'name': 'max_chapter', 'content': str(max_chapter)})
        book.set_cover(content=image, file_name='cover.jpg')
        book.add_metadata(None, 'meta', '', {'name': f'attribute', 'content': attribute})
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
        print(f'Tải thành công {i - 1}/{max_chapter} chap . File của bạn nằm ở "D:/novel"')
        if exit: break
