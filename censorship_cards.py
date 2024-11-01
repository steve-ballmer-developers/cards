import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ElementTree
import chompjs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd
from fake_useragent import UserAgent


class CensorshipCards:

    def __init__(self) -> None:

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Accept': 'application/xml, text/xml, */*; q=0.01',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Faces-Request': 'partial/ajax',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://invenio.bundesarchiv.de',
            'Connection': 'keep-alive',
            'Referer': 'https://invenio.bundesarchiv.de/invenio/main.xhtml',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

        self.session = requests.Session()

        self.onclick_regex = re.compile('^showLoading.*name:"id",value:"(.*)".*')

        self.js_film_object_regex = re.compile(r".*var data = (.*);")

        self.films = {}

        self.total_pages = -1

        self.user_agent = UserAgent()

    def setup_cookies_etc_with_selenium(self) -> None:

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument(f'user-agent={self.user_agent.random}')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(
            'https://invenio.bundesarchiv.de/invenio/direktlink/27e05414-f7d2-4a6f-bb78-904f466c1309/'
        )
        html_response = driver.page_source

        javax_faces_state_input_tag = self.validate_response_javax_faces_state(
            html_response
        )

        while javax_faces_state_input_tag == None:
            print('XXXX javax_faces_state_input_tag == None')
            time.sleep(600)
            driver.close()
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(
                'https://invenio.bundesarchiv.de/invenio/direktlink/27e05414-f7d2-4a6f-bb78-904f466c1309/'
            )
            html_response = driver.page_source
            javax_faces_state_input_tag = self.validate_response_javax_faces_state(
                html_response
            )

        self.javax_faces_view_state = javax_faces_state_input_tag.attrs.get('value')

        self.jsession_id = driver.get_cookie('JSESSIONID').get('value')

        self.cookies = {
            'JSESSIONID': self.jsession_id,
            'has_js': '1',
        }

        self.initial_request_payload = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'j_idt5794:j_idt5795',
            'javax.faces.partial.execute': '@all',
            'j_idt5794:j_idt5795': 'j_idt5794:j_idt5795',
            'j_idt5794': 'j_idt5794',
            'javax.faces.ViewState': self.javax_faces_view_state,
        }
        driver.close()
        time.sleep(1)

    def validate_response_javax_faces_state(self, html_response: str) -> str:
        soup = BeautifulSoup(html_response, 'html.parser')
        return soup.find('input', {'name': 'javax.faces.ViewState'})

    def page_payload(self, page: int):

        return {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'masterLayoutForm:tabPanel:tabSearchNavi:selectPageList',
            'javax.faces.partial.execute': 'masterLayoutForm:tabPanel:tabSearchNavi:selectPageList masterLayoutForm:tabPanel:tabSearchNavi:j_idt367',
            'javax.faces.partial.render': 'masterLayoutForm:tabPanel:tabSearchNavi:SelectButtonForm1 masterLayoutForm:tabPanel',
            'javax.faces.behavior.event': 'change',
            'javax.faces.partial.event': 'change',
            'masterLayoutForm': 'masterLayoutForm',
            'masterLayoutForm:usernameForgotPw': '',
            'masterLayoutForm:emailForgotPw': '',
            'masterLayoutForm:emailForgotKe': '',
            'masterLayoutForm:benutzungselectone': '1',
            'masterLayoutForm:benutzungselectoneEid': '1',
            'masterLayoutForm:j_idt127': '',
            'masterLayoutForm:j_idt129': '',
            'masterLayoutForm:tektonik:tree_selection': '',
            'masterLayoutForm:klassif:tree_selection': '',
            'masterLayoutForm:tabPanel:tabSearchNavi:selectPageList': str(page),
            'masterLayoutForm:tabPanel_activeIndex': '0',
            'javax.faces.ViewState': self.javax_faces_view_state,
        }

    def setup_session_retry(self) -> None:

        retries = Retry(
            total=2, backoff_factor=150, status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def count_pages(self, html_response: str) -> None:
        soup = BeautifulSoup(html_response, 'html.parser')
        option_elements = soup.find_all('option')
        return len((option_elements))

    def post_request(self, data) -> str:

        response = self.session.post(
            'https://invenio.bundesarchiv.de/invenio/main.xhtml',
            cookies=self.cookies,
            headers=self.headers,
            data=data,
        )
        print('XXXX', 'https://invenio.bundesarchiv.de/invenio/main.xhtml')
        print('XXXX', response.status_code)
        time.sleep(1)
        return response.text

    def get_request(self, url: str) -> str:
        response = self.session.get(url, cookies=self.cookies, headers=self.headers)
        print('XXXX', url)
        print('XXXX', response.status_code)
        time.sleep(1)
        return response.text

    def extract_html_from_xml(self, xml_response: str, request_payload: dict) -> str:
        root = ElementTree.fromstring(xml_response)
        update_tags = root.findall('.//update')
        # print(update_tags[0].text)

        while len(update_tags) == 0:
            print('XXXX while len(update_tags) == 0:')

            time.sleep(600)
            self.setup_cookies_etc_with_selenium()
            xml_response = self.post_request(request_payload)
            root = ElementTree.fromstring(xml_response)
            update_tags = root.findall('.//update')

        return update_tags[0].text

    def extract_archivsignatur(self, detail) -> str:
        spans = detail.find_all('span', class_='detail-archivsignatur')
        return spans[0].text

    def extract_titel(self, detail) -> str:
        divs = detail.find_all('div', class_='detail-titel')
        return divs[0].text

    def parse_description_list(self, detail):
        dts = [dt.text.strip() for dt in detail.find_all('dt')]
        dts.pop()
        dds = [dd.text.strip() for dd in detail.find_all('dd')]
        return dict(zip(dts, dds))

    def parse_films_html(self, html_response: str) -> list:
        soup = BeautifulSoup(html_response, 'html.parser')
        film_details = soup.find_all('li', class_='detail-listlevel-0')

        count = 0
        even = []
        odd = []
        ids = []
        for detail in film_details:
            if count % 2 == 0:
                film = {}
                film['archivsignatur'] = self.extract_archivsignatur(detail)
                film['titel'] = self.extract_titel(detail)
                even.append(film)
            else:
                film = self.parse_description_list(detail)
                odd.append(film)
                digitalisat_link = detail.find_all('a', class_='detail-digitalisatLink')
                m = self.onclick_regex.match(digitalisat_link[0].get('onclick'))
                ids.append(m.group(1))
            count += 1

        return dict(zip(ids, [even[i] | odd[i] for i in range(len(even))]))

    def extract_image_urls(self, film_metadata: dict) -> None:
        for film_id in film_metadata.keys():

            url = f'https://invenio.bundesarchiv.de/invenio/invenio-viewer/lixe/view/{film_id}#item=0&page=0'
            response = self.get_request(url)

            m = self.js_film_object_regex.findall(response)
            js_object = m[0]
            card_data = chompjs.parse_js_object(js_object)
            card_images = []
            for file in card_data.get('items')[0].get('files'):
                card_images.append(
                    f'https://invenio.bundesarchiv.de/invenio/invenio-viewer/lixe/files/{card_data.get("path")}/{file.get("filename")}'
                )

            self.films[film_id] = film_metadata[film_id]
            self.films[film_id]['images'] = card_images

    def iterate_over_pages(self):
        print('XXXX PAGE 0')
        initial_xml_response = self.post_request(self.initial_request_payload)
        initial_film_metadata = self.extract_film_metadata(
            initial_xml_response, self.initial_request_payload
        )
        self.extract_image_urls(initial_film_metadata)
        self.generate_csv()
        time.sleep(1)

        # for page in range(2, 5):
        # for page in range(2, self.total_pages + 1):
        # for page in range(105, self.total_pages + 1):
        for page in range(128, self.total_pages + 1):
            print('XXXX PAGE ', str(page))
            xml_response = self.post_request(self.page_payload(page))
            film_metadata = self.extract_film_metadata(
                xml_response, self.page_payload(page)
            )
            self.extract_image_urls(film_metadata)
            self.generate_csv()
            time.sleep(1)

    def extract_film_metadata(self, xml_response: str, request_payload: dict) -> dict:

        html_response = self.extract_html_from_xml(xml_response, request_payload)

        if self.total_pages < 0:

            self.total_pages = self.count_pages(html_response)

        film_metadata = self.parse_films_html(html_response)

        return film_metadata

    def generate_csv(self):

        df = pd.DataFrame.from_dict(self.films, orient='index')
        df.to_csv('/home/user/file.csv')


if __name__ == '__main__':

    censorship_cards = CensorshipCards()
    censorship_cards.setup_cookies_etc_with_selenium()
    censorship_cards.setup_session_retry()
    censorship_cards.iterate_over_pages()
    censorship_cards.generate_csv()
