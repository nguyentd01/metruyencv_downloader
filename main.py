import httpx
from bs4 import BeautifulSoup
from ebooklib import epub
import asyncio
import os
import gc
from async_lru import alru_cache
import backoff
from user_agent import get
from tqdm.asyncio import tqdm


# Set up global httpx settings for better performance
disk = str(input('Ổ đĩa lưu truyện(C/D):')).capitalize()
max_connections = int(input('''Max Connections (10 -> 1000) 
Note: Càng cao thì rủi ro lỗi cũng tăng, chỉ số tối ưu nhất là 50 : '''))
limits = httpx.Limits(max_keepalive_connections=0, max_connections=max_connections)
timeout = httpx.Timeout(None)
client = httpx.AsyncClient(limits=limits, timeout=timeout)

 # Enable garbage collection
gc.enable()

# Base URL for the novel
BASE_URL = 'https://metruyencv.com/truyen/'

user_agent = get()

header = {'user-agent': user_agent}


def sort_chapters(list_of_chapters):
    lst = len(list_of_chapters)
    for i in range(0, lst):
        for j in range(0, lst - i - 1):
            if (list_of_chapters[j][2] > list_of_chapters[j + 1][2]):
                temp = list_of_chapters[j]
                list_of_chapters[j] = list_of_chapters[j + 1]
                list_of_chapters[j + 1] = temp
    return list_of_chapters


# Retry decorator for handling transient errors, excluding 404 errors
@backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=3, giveup=lambda e: e.response.status_code == 404)
async def get_chapter_with_retry(chapter_number, novel_url):
    url = f'{novel_url}/chuong-{chapter_number}'
    i = 0
    try:
        while True:
            resp = await client.get(url, headers=header)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'lxml')
            chapter_content = soup.find('div', class_='break-words')
            chapter_title = soup.find('h2', class_='text-center text-gray-600 dark:text-gray-400 text-balance')
            html = str(chapter_content)
            await asyncio.sleep(1)
            if html.count("<br/>") != 8:
                break
            else:
                i += 1
                if i == 10:
                    return None

        if html is None or chapter_title is None:
            print(f"""
Lỗi: Không thể tìm thấy chapter {chapter_number}, đang bỏ qua...""")
            return None

        await asyncio.sleep(1)
        return str(chapter_title), html, chapter_number
    except httpx.HTTPError as e:
        if e.response.status_code == 404:
            print(f"""
Lỗi: Không thể tìm thấy chapter {chapter_number} (404), đang bỏ qua...""")
            return None
        else:
            print(f"HTTP error fetching chapter {chapter_number}: {e}. Đang thử lại...")
            await asyncio.sleep(5)
            raise


# Cache the results of the 'get' function for better performance
@alru_cache(maxsize=1024)
async def fetch_chapters(start_chapter, end_chapter, novel_url):
    tasks = [get_chapter_with_retry(number, novel_url) for number in range(start_chapter, end_chapter + 1)]
    # Use tqdm to display a progress bar
    chapters = []
    async for future in tqdm(asyncio.as_completed(tasks), total=end_chapter - start_chapter + 1, desc="Tải chapters...",
                             unit=" chapters"):
        chapter = await future  # Await here to get the actual result
        if chapter is not None:
            chapters.append(chapter)
    sorted_chapters = sort_chapters(chapters)
    return sorted_chapters


def create_epub(title, author, status, attribute, image, chapters, path, filename):
    book = epub.EpubBook()
    book.set_title(title)
    book.set_identifier("nguyentd010")
    book.add_author(author)
    book.set_language('vn')
    book.add_metadata(None, 'meta', '', {'name': 'status', 'content': status})
    book.add_metadata(None, 'meta', '', {'name': 'chapter', 'content': str(len(chapters))})
    book.set_cover(content=image, file_name='cover.jpg')
    book.add_metadata(None, 'meta', '', {'name': 'attribute', 'content': attribute})
    num = 1
    chapter_num = []
    for chapter_title, chapter, i in chapters:
        chapter_num.append(i)
        chapter_title = BeautifulSoup(chapter_title, 'lxml').text
        chapter = f'<h2>{chapter_title}</h2>' + chapter
        if num == 1:
            chapter = f'<h1>{title}</h1>' + chapter
        num += 1
        html = BeautifulSoup(chapter, 'lxml')
        file_name = f'chapter{i}.html'
        chapter = epub.EpubHtml(lang='vn', title=chapter_title, file_name=file_name, uid=f'chapter{i}')
        chapter.content = str(html)
        book.add_item(chapter)

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

    book.spine = [f'chapter{i}' for i in chapter_num]
    epub.write_epub(f'{path}/{filename}.epub', book)


async def main():
    while True:
        novel_url = input('Nhập link metruyencv mà bạn muốn tải: ')
        if '/' == novel_url[-1]:
            novel_url = novel_url[:-1]
        start_chapter = int(input('Chapter bắt đầu: '))
        end_chapter = int(input('Chapter kết thúc: '))

        try:
            response = await client.get(novel_url, headers=header)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            title = str(soup.find('h1', class_='mb-2').text)
            author = str(soup.find('a', class_='text-gray-500').text).strip()
            status = str(
                soup.find('a', class_='inline-flex border border-primary rounded px-2 py-1 text-primary').select_one(
                    'span').text).strip()
            attribute = str(soup.find('a',
                                      class_='inline-flex border border-rose-700 dark:border-red-400 rounded px-2 py-1 text-rose-700 dark:text-red-400').text)
            image_url = soup.find('img', class_='w-44 h-60 shadow-lg rounded mx-auto')['src']
        except (httpx.HTTPError, TypeError, KeyError) as e:
            print(f"Error fetching novel information: {e}")
            continue

        try:
            image_data = await client.get(image_url, headers=header)
            image_data.raise_for_status()
            image = image_data.content
        except httpx.HTTPError as e:
            print(f"Error downloading image: {e}")
            continue

        filename = novel_url.replace(BASE_URL, '').replace('-', '')
        path = f"{disk}:/novel/{title.replace(':', ',').replace('?', '')}"
        os.makedirs(path, exist_ok=True)

        chapters = await fetch_chapters(start_chapter, end_chapter, novel_url)
        valid_chapters = [chapter for chapter in chapters if chapter is not None]

        if valid_chapters:
            create_epub(title, author, status, attribute, image, valid_chapters, path, filename)
            print(
                f'Tải thành công {len(valid_chapters)}/{end_chapter - start_chapter + 1} chapter. File của bạn nằm tại "D:/novel"')
        else:
            print("Lỗi. Tải không thành công")

        if input("Tải tiếp? (y/n): ").lower() != 'y':
            break


if __name__ == '__main__':
    asyncio.run(main())
