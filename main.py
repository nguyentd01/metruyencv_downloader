import httpx
from bs4 import BeautifulSoup
from ebooklib import epub
import asyncio
from user_agent import get
from tqdm.asyncio import tqdm
from playwright.async_api import async_playwright
import pytesseract
from PIL import Image
from PIL import ImageEnhance
import io
from appdirs import *
import configparser
import os.path
import gc



gc.enable()
data_dir = user_config_dir(appname='metruyencv-downloader',appauthor='nguyentd010')
print(data_dir)
os.makedirs(data_dir, exist_ok=True)
if not os.path.isfile(data_dir + '\config.ini'):
    config = configparser.ConfigParser()
    with open(data_dir + '\config.ini', 'w') as configfile:
        config.write(configfile)

try:
    config = configparser.ConfigParser()
    config.read(data_dir + '\config.ini')
    username = str(config.get('data', 'login'))
    password = str(config.get('data', 'password'))
    disk = str(config.get('data', 'disk'))
    max_tabs = int(config.get('data', 'max-tabs'))
    save = None
except:
    username = str(input('Email tài khoản metruyencv?:'))
    password = str(input('Password?:'))
    disk = str(input('Ổ đĩa lưu truyện(C/D):')).capitalize()
    max_tabs = int(input('''Number of Browser tabs:'''))
    save = str(input('Lưu config?(Y/N):')).capitalize()



timeout = httpx.Timeout(None)
client = httpx.AsyncClient(timeout=timeout)

# Base URL for the novel
BASE_URL = 'https://metruyencv.com/truyen/'

user_agent = get()

file_location = os.getcwd()

pytesseract.pytesseract.tesseract_cmd = fr'{file_location}\Tesseract-OCR\tesseract.exe'

header = {'user-agent': user_agent}

if save == 'Y':
    config = configparser.ConfigParser()
    config['data'] = {'login': username, 'password': password, 'disk' : disk, 'max-tabs' : max_tabs}

    # Write the configuration to a file
    with open(data_dir + '\config.ini', 'w') as configfile:
        config.write(configfile)


def ocr(image: bytes) -> str:
    image = Image.open(io.BytesIO(image))
    converted_img = ImageEnhance.Contrast(image.convert("L")).enhance(1.5)
    text = pytesseract.image_to_string(converted_img, lang='vie')
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

async def handle_route(route):
  if "https://googleads" in route.request.url or "https://adclick" in route.request.url:
    await route.abort()
  else:
    await route.continue_()

async def login(context,novel_url):
    page = await context.new_page()
    await page.goto(novel_url,timeout=0)
    await page.locator('xpath=/html/body/div[1]/header/div/div/div[3]/button').click()
    await page.locator(
        'xpath=/html/body/div[1]/div[2]/div/div[2]/div/div/div/div/div[2]/div[1]/div/div[1]/button').click()
    await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[2]/input').fill(username)
    await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div[2]/input').fill(password)
    await page.locator('xpath=/html/body/div[1]/div[3]/div[2]/div/div/div[2]/div[3]/div[1]/button').click()
    await page.locator('xpath=/html/body/div[1]/div[2]/div/div[2]/div/div/div/div/div[1]/div/div[2]/button').click()
    await page.locator('xpath=/html/body/div[1]/div[1]/div/main/div[3]/div[1]/button[1]').click()
    await page.reload()
    await asyncio.sleep(1)
    await page.locator('xpath=/html/body/div[1]/div[1]/div/main/div[3]/div[1]/button[1]').click()
    await page.locator('xpath=/html/body/div[1]/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[3]/select').select_option(value ='Arial')
    await page.locator('xpath=/html/body/div[1]/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[4]/select').select_option(value='25px')
    await page.locator('xpath=/html/body/div[1]/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div/div[2]/div[5]/select').select_option(value='130%')
    await page.close()


async def info(context,novel_url):
    page = await context.new_page()
    await page.goto(novel_url,timeout=0)
    html = await page.content()
    soup = BeautifulSoup(html,'lxml')
    title = str(soup.find('h1', class_='mb-2').text)
    author = str(soup.find('a', class_='text-gray-500').text).strip()
    status = str(
        soup.find('a', class_='inline-flex border border-primary rounded px-2 py-1 text-primary').select_one(
            'span').text).strip()
    attribute = str(soup.find('a',
                                class_='inline-flex border border-rose-700 dark:border-red-400 rounded px-2 py-1 text-rose-700 dark:text-red-400').text)
    
    image_url = soup.find('img', class_='w-44 h-60 shadow-lg rounded mx-auto')['src']
    desc = str(soup.find('div',class_='text-gray-600 dark:text-gray-300 py-4 px-2 md:px-1 text-base break-words').text)
    return title, author, status, attribute, image_url,desc



async def download_chapter(num, novel_url, context, asyncio_semaphore):
    async with asyncio_semaphore:
        link = f'{novel_url}/chuong-{num}'
        page = await context.new_page()
        await page.goto(link,timeout=0)
        loadmore_element1 = await page.wait_for_selector('xpath=/html/body/div[1]/div[1]/div/main/div[4]/div[1]', state='visible')
        content = await page.content()
        soup = BeautifulSoup(content,'lxml')
        title = str(soup.find('h2', class_='text-center text-gray-600 dark:text-gray-400 text-balance').text)
        missing_html = await loadmore_element1.inner_html()
        missing_html = BeautifulSoup(str(missing_html),'lxml')
        images = await page.query_selector_all('canvas')
        for image in images:
            image_bytes = await image.screenshot()
            ocr_result = await asyncio.to_thread(ocr, image_bytes)
            missing_html.find('canvas').replace_with(ocr_result)
        missing_html = str(missing_html).replace('<br/><br/>', '<br/>').replace('<br/>', '<br/><br/>').replace('\n', ' ').replace("·","")
        await page.close()
        return (title,missing_html,num)


def sort_chapters(list_of_chapters):
    lst = len(list_of_chapters)
    for i in range(0, lst):
        for j in range(0, lst - i - 1):
            if (list_of_chapters[j][2] > list_of_chapters[j + 1][2]):
                temp = list_of_chapters[j]
                list_of_chapters[j] = list_of_chapters[j + 1]
                list_of_chapters[j + 1] = temp
    return list_of_chapters


async def fetch_chapters(start_chapter, end_chapter, novel_url):
    async with async_playwright() as p:
        print(f'Logining...')
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await login(context,f'{novel_url}/chuong-{start_chapter}')
        asyncio_semaphore = asyncio.Semaphore(max_tabs)
        tasks1 = [download_chapter(number, novel_url, context,asyncio_semaphore) for number in range(start_chapter, end_chapter + 1)]
        chapters = []
        # Use tqdm to display a progress bar
        async for future in tqdm(asyncio.as_completed(tasks1), total=end_chapter - start_chapter + 1, desc="Tải chapters...",
                                unit=" chapters"):
            chapter = await future  # Await here to get the actual result
            if chapter is not None:
                chapters.append(chapter)
    chapters = delete_dupe(chapters)
    sorted_chapters = sort_chapters(chapters)
    return sorted_chapters


def create_epub(title, author, status, attribute, image, chapters, path, filename,desc):
    book = epub.EpubBook()
    book.set_title(title)
    book.set_identifier("nguyentd010")
    book.add_author(author)
    book.set_language('vi')
    book.add_metadata('DC', 'creator', 'nguyentd010')
    book.add_metadata('DC', 'publisher', 'nguyentd010')
    book.add_metadata('DC', 'description', desc)
    book.add_metadata(None, 'meta', '', {'name': 'status', 'content': status})
    book.add_metadata(None, 'meta', '', {'name': 'chapter', 'content': str(len(chapters))})
    book.set_cover(content=image, file_name='cover.jpg')
    book.add_metadata(None, 'meta', '', {'name': 'attribute', 'content': attribute})
    p = 1
    chapter_num = []
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
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            title, author, status, attribute, image_url,desc = await info(context,novel_url)
        image_data = await client.get(image_url, headers=header)
        image_data.raise_for_status()
        image = image_data.content

        filename = novel_url.replace(BASE_URL, '').replace('-', '')
        path = f"{disk}:/novel/{title.replace(':', ',').replace('?', '')}"
        os.makedirs(path, exist_ok=True)

        chapters = await fetch_chapters(start_chapter, end_chapter, novel_url)
        valid_chapters = [chapter for chapter in chapters if chapter is not None]

        if valid_chapters:
            create_epub(title, author, status, attribute, image, valid_chapters, path, filename,desc)
            print(
                f'Tải thành công {len(valid_chapters)}/{end_chapter - start_chapter + 1} chapter. File của bạn nằm tại "D:/novel"')
        else:
            print("Lỗi. Tải không thành công")

        if input("Tải tiếp? (y/n): ").lower() != 'y':
            break


if __name__ == '__main__':
    asyncio.run(main())
