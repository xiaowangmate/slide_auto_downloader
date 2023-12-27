import os
import re
import json
import requests
from bs4 import BeautifulSoup


class SlideDownloader:
    def __init__(self):
        self.cookie_path = "./conditions/cookie.txt"
        self.slide_category_list_path = "./conditions/slideCategoryList.json"
        self.slides_output_folder = "./output/slides"
        self.jsonl_output_folder = "./output/jsonl"
        self.crawled_urls_record_path = "./record/crawled_urls_record.txt"
        self.slide_info_record_jsonl = "slide_info_record.jsonl"
        self.slide_info_record_jsonl_path = f"{self.jsonl_output_folder}/{self.slide_info_record_jsonl}"

        self.cookie = self.read_cookie()
        self.slide_category_list = self.read_slide_categories()
        self.saved_slide_info_list = self.get_saved_slide_info_list()
        self.crawled_url_list = self.get_crawled_url_list()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.46",
            "Cookie": self.cookie
        }

    def read_cookie(self):
        with open(self.cookie_path, mode="r", encoding="utf-8") as r:
            cookie = r.read()
            return cookie

    def read_slide_categories(self):
        with open(self.slide_category_list_path, mode="r", encoding="utf-8") as r:
            slide_category_list = json.loads(r.read())
            return slide_category_list

    def get_saved_slide_info_list(self):
        if not os.path.exists(self.slide_info_record_jsonl_path):
            with open(self.slide_info_record_jsonl_path, mode="w", encoding="utf-8") as w:
                w.write("")
            saved_slide_info_list = []
        else:
            with open(self.slide_info_record_jsonl_path, mode="r", encoding="utf-8") as r:
                saved_slide_info_list = r.read().split("\n")
        return saved_slide_info_list

    def get_crawled_url_list(self):
        with open(self.crawled_urls_record_path, mode="r", encoding="utf-8") as r:
            crawled_url_list = r.read().split("\n")
            return crawled_url_list

    def get_csrf_token(self):
        csrf_token_verified_url = "https://www.slideshare.net/csrf_token"
        csrf_token = requests.get(csrf_token_verified_url, headers=self.headers).content
        csrf_token = json.loads(csrf_token)["csrf_token"]
        return csrf_token

    def start_crawl_all_url(self, init_link):
        response = requests.get(init_link, headers=self.headers).text
        soup = BeautifulSoup(response, "html.parser")
        self.crawl_all_url(soup)

    def crawl_all_url(self, soup):
        all_urls = soup.find_all('a')
        for url in all_urls:
            href = url.get('href')
            if href:
                if re.findall("https://www.slideshare.net/.*?/.*",
                              href) and '#' not in href and href != 'https://www.slideshare.net/rss/latest':
                    if href not in self.crawled_url_list:
                        print(f"crawl url: {href}")
                        self.append_crawled_list(href)
                        self.get_slide_info(href)

    def get_slide_info(self, slide_link):
        response = requests.get(slide_link, headers=self.headers).text
        soup = BeautifulSoup(response, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        script_string = script_tag.string
        script_json = json.loads(script_string)
        # print(f"script json: {script_json}")
        pageProps = script_json["props"]["pageProps"]

        if "slideshow" in pageProps.keys():
            slide_show = pageProps["slideshow"]
            allowDownloads = slide_show["allowDownloads"]
            if allowDownloads:
                download_key = slide_show["downloadKey"]
                slideshow_id = slide_show["id"]
                slide_download_url = self.get_slide_download_url(slide_link, download_key, slideshow_id)
                if slide_download_url:
                    self.download_slide(slideshow_id, slide_download_url)
                    json_info = {
                        "name": f"{slideshow_id}.pdf",
                        "title": slide_show["strippedTitle"],
                        "description": slide_show["description"],
                        "categories": slide_show["categories"],
                        "link": slide_show["canonicalUrl"],
                        "likes": slide_show["likes"],
                        "views": soup.select(".MetadataAbovePlayer_root__2cGVN .Likes_root__WVQ1_")[-1].text.replace(
                            " views", ""),
                        "creation_time": slide_show["createdAt"],
                        "sharer": slide_show["username"]
                    }
                    self.append_jsonl(json.dumps(json_info, ensure_ascii=False))
                    self.append_crawled_list(slide_link)

        self.crawl_all_url(soup)
        print("-" * 50)

    def get_slide_download_url(self, slide_link, download_key, slideshow_id):
        mock_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Length": "0",
            "Cookie": self.cookie,
            "Origin": "https://www.slideshare.net",
            "Referer": slide_link,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "Windows",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Csrf-Token": self.get_csrf_token()
        }
        verify_url = f"https://www.slideshare.net/slideshow/download?download_key={download_key}&slideshow_id={slideshow_id}"
        response = requests.post(verify_url, headers=mock_headers).content
        response = json.loads(response)
        slide_download_url = None
        if response["success"]:
            slide_download_url = response["url"]
            print(f"slide download url: {slide_download_url}")
        return slide_download_url

    def download_slide(self, slideshow_id, slide_download_url):
        response = requests.get(slide_download_url, headers=self.headers)
        slide_download_path = f"{self.slides_output_folder}/{slideshow_id}.pdf"
        if not os.path.exists(slide_download_path):
            with open(slide_download_path, mode="wb") as w:
                w.write(response.content)
        else:
            print("slide already downloaded.")

    def append_jsonl(self, json_info):
        if json_info not in self.saved_slide_info_list:
            with open(self.slide_info_record_jsonl_path, mode="a+", encoding="utf-8") as w:
                w.write(json_info + "\n")
                self.saved_slide_info_list.append(json_info)
                print(f"write json info: {json_info} successful.")
        else:
            print("json info already wrote.")

    def append_crawled_list(self, crawled_url):
        with open(self.crawled_urls_record_path, mode="a+", encoding="utf-8") as w:
            w.write(crawled_url + "\n")
            self.crawled_url_list.append(crawled_url)
            print(f"write crawled url: {crawled_url}.")


if __name__ == '__main__':
    sd = SlideDownloader()
    # sd.get_slide_info("https://www.slideshare.net/stinsondesign/10-things-your-audience-hates-about-your-presentation")
    sd.start_crawl_all_url("https://www.slideshare.net/")
