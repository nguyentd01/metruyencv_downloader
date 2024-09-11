import httpx
from bs4 import BeautifulSoup
from ebooklib import epub
import asyncio
from user_agent import get
from tqdm.asyncio import tqdm
import backoff
from playwright.async_api import async_playwright
import pytesseract
from PIL import Image
import io
from appdirs import *
import configparser
import os.path
import gc
from async_lru import alru_cache



# Enable garbage collection
gc.enable()
data_dir = user_config_dir(appname='metruyencv-downloader',appauthor='nguyentd010')
os.makedirs(data_dir, exist_ok=True)
if not os.path.isfile(data_dir + '\config.ini'):
    config = configparser.ConfigParser()
    with open(data_dir + '\config.ini', 'w') as configfile:
        config.write(configfile)


if os.stat(data_dir+"\config.ini").st_size == 0:
    username = str(input('Email tài khoản metruyencv?:'))
    password = str(input('Password?:'))
    disk = str(input('Ổ đĩa lưu truyện(C/D):')).capitalize()
    max_connections = int(input('''Max Connections (10 -> 1000) 
    Note: Càng cao thì rủi ro lỗi cũng tăng, chỉ số tối ưu nhất là 50 : '''))
    save = str(input('Lưu config?(Y/N):')).capitalize()

else:
    config = configparser.ConfigParser()
    config.read(data_dir + '\config.ini')
    username = str(config.get('data', 'login'))
    password = str(config.get('data', 'password'))
    disk = str(config.get('data', 'disk'))
    max_connections = int(config.get('data', 'max-connection'))
    save = None


limits = httpx.Limits(max_keepalive_connections=100, max_connections=max_connections)
timeout = httpx.Timeout(None)
client = httpx.AsyncClient(limits=limits, timeout=timeout)

# Base URL for the novel
BASE_URL = 'https://metruyencv.info/truyen/'

user_agent = get()

file_location = os.getcwd()

pytesseract.pytesseract.tesseract_cmd = fr'{file_location}\Tesseract-OCR\tesseract.exe'

header = {'user-agent': user_agent}

if save == 'Y':
    config = configparser.ConfigParser()
    config['data'] = {'login': username, 'password': password, 'disk' : disk, 'max-connection' : max_connections}

    # Write the configuration to a file
    with open(data_dir + '\config.ini', 'w') as configfile:
        config.write(configfile)


def ocr(image: bytes) -> str:
    image = Image.open(io.BytesIO(image))
    image = image.convert('L')
    text = pytesseract.image_to_string(image, lang='vie')
    return text


def delete_dupe(list):
    list1 = list.copy()
    l = []
    num = 0
    for i, j, k in list1:
        if k in l:
            del list1[num]
        l.append(i)
        num += 1
    return list1


async def download_chapter(semaphore,context,title,link,num):
    async with semaphore:
        page = await context.new_page()
        await page.goto(link,timeout=0)
        await page.route("**/*", handle_route)
        await page.wait_for_selector('xpath=/html/body/div[1]/main/div[4]/div[1]', state='attached',timeout=600000)
        image = await page.locator('xpath=/html/body/div[1]/main/div[4]').screenshot()
        await page.close()
        return title, image, num


async def handle_route(route):
  if "https://googleads" in route.request.url or "https://adclick" in route.request.url:
    await route.abort()
  else:
    await route.continue_()


async def download_missing_chapter(links):
    results = []
    link = links[0][1]
    asyncio_semaphore = asyncio.Semaphore(10)
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(link)
        await page.locator('xpath=/html/body/div[1]/header/div/div/div[3]/button').click()
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/div[2]/div/div[2]/div/div/div/div/div[2]/div[1]/div/div[1]/button').click()
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[2]/input').fill(username)
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div[2]/input').fill(password)
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[3]/div[1]/button').click()
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/div[2]/div/div[2]/div/div/div/div/div[1]/div/div[2]/button').click()
        await asyncio.sleep(0.2)
        await page.locator('xpath=/html/body/div[1]/main/div[3]/div[1]/button[1]').click()
        await asyncio.sleep(0.2)
        await page.locator(
            'xpath=/html/body/div[1]/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[3]/select').select_option(
            value='Arial')
        await asyncio.sleep(0.2)
        await page.locator(
            'xpath=/html/body/div[1]/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[4]/select').select_option(
            value='25px')
        await asyncio.sleep(0.2)
        await page.locator(
            'xpath=/html/body/div[1]/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[5]/select').select_option(
            value='150%')
        await asyncio.sleep(0.2)
        await page.close()
        tasks = [asyncio.create_task(download_chapter(asyncio_semaphore, context, title, link, num)) for title,link,num in links]
        async for task in tqdm(asyncio.as_completed(tasks), total=len(tasks),desc="Tải chapters bị thiếu...",unit=" chapters"):
            result = await task
            title = result[0]
            image = result[1]
            num = result[2]
            ocr_result = await asyncio.to_thread(ocr,image)
            missing_html = str(ocr_result).replace('\n\n', '<br/><br/>').replace('\n', ' ')
            results.append((title, missing_html, num))
        await context.close()
        await browser.close()
    return results


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
            chapter_title = str(soup.find('h2', class_='text-center text-gray-600 dark:text-gray-400 text-balance'))
            html = str(chapter_content)
            if html.count("<br/>") != 8:
                break
            else:
                i += 1
                if i == 15:
                    missing_chapter.append((chapter_title,url,chapter_number))
                    return None

        if html is None or chapter_title is None:
            print(f"""
Lỗi: Không thể tìm thấy chapter {chapter_number}, đang bỏ qua...""")
            return None

        return chapter_title, html, chapter_number
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
    tasks1 = [get_chapter_with_retry(number, novel_url) for number in range(start_chapter, end_chapter + 1)]
    chapters = []
    # Use tqdm to display a progress bar
    async for future1 in tqdm(asyncio.as_completed(tasks1), total=end_chapter - start_chapter + 1, desc="Tải chapters...",
                             unit=" chapters"):
        chapter = await future1  # Await here to get the actual result
        if chapter is not None:
            chapters.append(chapter)
    if missing_chapter != []:
        chapters += await download_missing_chapter(missing_chapter)
    chapters = delete_dupe(chapters)
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
    p = 1
    chapter_num = []
    loading_bar = tqdm(total=len(chapters),unit= ' chapters',desc='Tạo epub...')
    for chapter_title, chapter, i in chapters:
        chapter_num.append(i)
        chapter_title = BeautifulSoup(chapter_title, 'lxml').text
        chapter = f'<h2>{chapter_title}</h2>' + "<h3>Generated by nguyentd010's metruyencv_downloader</h3>" + chapter
        if p == 1:
            chapter = f"<h1>{title}</h1>" + chapter
        p += 1
        html = BeautifulSoup(chapter, 'lxml')
        file_name = f'chapter{i}-{chapter_title}.html'
        chapter = epub.EpubHtml(lang='vn', title=chapter_title, file_name=file_name, uid=f'chapter{i}')
        chapter.content = str(html)
        book.add_item(chapter)
        loading_bar.update(1)

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
        global missing_chapter
        missing_chapter = []
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
        missing_chapter.clear()
        fetch_chapters.cache_clear()


if __name__ == '__main__':
    asyncio.run(main())
