import time
import re

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd

base_url = "https://yacht-parts.ru"
catalog_url = f"{base_url}/catalog"

response = requests.get(catalog_url)
soup = BeautifulSoup(response.text, 'lxml')
categories = soup.find_all('li', class_='sect')  # Находит все категории


def get_category(content):
    if content:
        name_category = content.find_all('span', itemprop='itemListElement')
    else:
        return ''
    res = name_category[-2].find('span', itemprop="name").text
    if name_category:
        return res
    return ''


def get_article(content):
    return content.find('div', class_='article iblock') \
        .find('span', class_='value').text.strip()  


def get_brand(content):
    brand_tag = content.find('a', class_='brand_picture')
    if brand_tag and brand_tag.find('img'):
        return brand_tag.get('title', 'Нет бренда').strip()
    return 'Нет бренда'


def get_product_name(soup):
    return soup.find('h1', id='pagetitle').text.strip()


def get_price(soup):
    price_div = soup.find('div', class_='price')
    if price_div and price_div.text.strip():
        price_text = re.sub(r'\D', '', price_div.text.strip())
        return int(price_text) if price_text.isdigit() else 'Неизвестно'
    return 'Неизвестно'


def get_description(soup):
    preview_div = soup.find('div', class_='preview_text')
    if preview_div:
        return preview_div.text.strip()
    return 'Нет описания.'


def get_images(soup, base_url):
    images_div = soup.find('div', class_='slides')
    if images_div:  # Проверяем, что div найден
        images = images_div.find_all('img')  
        return ', '.join([f"{img['src']}" for img in images if 'src' in img.attrs])  # Формируем ссылки
    return ""  # Если div не найден, возвращаем пустую строку


def parse_product_page(product_url, base_url):
    # Основная функция для парсинга страницы товара
    product_data = {}

    session = requests.Session()
    retries = \
        Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    response = session.get(product_url, timeout=30)

    soup = BeautifulSoup(response.text, 'lxml')
    content = soup.find('div', class_='container')

    product_category = get_category(content)
    product_data['Категория'] = product_category
    product_data['Артикуль'] = get_article(content)
    product_data['Бренд'] = get_brand(content)
    product_data['Наименование товара'] = get_product_name(soup)
    product_data['Цена'] = get_price(soup)
    product_data['описание'] = get_description(soup)
    product_data['ссылка на изображение'] = get_images(soup, base_url)

    return product_data


def get_next_page(soup):
    # Функция для поиска ссылки на следующую страницу
    next_page = soup.find('li', class_='flex-nav-next')
    if next_page and next_page.find('a'):
        return next_page.find('a')['href']
    return None


def save_data():
    # Сохраняем данные в таблицу
    df = pd.DataFrame(all_products)
    df.to_excel("catalog.xlsx", index=False)
    print("Данные сохранены в файл catalog.xlsx")


all_products = []
i = 0
#  Проходим по всем категориям и по кажому товару в категории
for category in categories:
    category_link = f"{base_url}{category.find('a')['href']}"

    while category_link:
        try:
            response = requests.get(category_link)
            soup = BeautifulSoup(response.text, 'lxml')
            items = soup.find_all('div', class_='list_item_wrapp item_wrap')

            for item in items:
                item_href = item.find('div', class_='item-title').find('a')['href']
                product_link = f"{base_url}{item_href}"

                try:
                    all_products.append(parse_product_page(product_link, base_url))
                except requests.exceptions.RequestException as e:
                    print("Ошибка при парсинге товара:", e)
                    save_data()  # Сохраняем данные при ошибке
                    continue

                time.sleep(1)  # Добавляем задержку, чтобы не перегружать сервер
                i += 1
                print('Количество спарсированных страниц: ', i)

            # Получаем ссылку на следующую страницу, если она есть
            next_page = get_next_page(soup)
            category_link = f"{base_url}{next_page}" if next_page else None
            print(f'Ссылка: {category_link}')


        except requests.exceptions.RequestException as e:
            print("Ошибка при загрузке категории:", e)
            save_data()  # Сохраняем данные при ошибке
            break  # Переходим к следующей категории, если есть

save_data()
