import os
import re
import json
import time
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
        self.slide_data_api = "https://api.slidesharecdn.com/graphql"

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

    def get_slide_info(self, slide_link):
        response = requests.get(slide_link, headers=self.headers).text
        soup = BeautifulSoup(response, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        script_string = script_tag.string
        script_json = json.loads(script_string)
        # print(f"script json: {script_json}")
        page_props = script_json["props"]["pageProps"]

        if "slideshow" in page_props.keys():
            slide_show = page_props["slideshow"]
            allow_downloads = slide_show["allowDownloads"]
            if allow_downloads:
                download_key = slide_show["downloadKey"]
                slideshow_id = slide_show["id"]
                slide_title = slide_show["strippedTitle"]
                slider_likes = slide_show["likes"]
                if self.slide_filter(slide_title, slider_likes):
                    slide_download_url = self.get_slide_download_url(slide_link, download_key, slideshow_id)
                    if slide_download_url:
                        if "limit of 100 downloads in last 24 hours" not in slide_download_url:
                            self.download_slide(slideshow_id, slide_download_url)
                            json_info = {
                                "name": f"{slideshow_id}.pdf",
                                "title": slide_title,
                                "description": slide_show["description"],
                                "categories": slide_show["categories"],
                                "link": slide_show["canonicalUrl"],
                                "likes": slider_likes,
                                "views": soup.select(".MetadataAbovePlayer_root__2cGVN .Likes_root__WVQ1_")[
                                    -1].text.replace(
                                    " views", ""),
                                "creation_time": slide_show["createdAt"],
                                "sharer": slide_show["username"],
                                "total_slides": slide_show["totalSlides"]
                            }
                            self.append_jsonl(json.dumps(json_info, ensure_ascii=False))
                            self.append_crawled_list(slide_link)
                        else:
                            raise ValueError("limit of 100 downloads in last 24 hours")
                    else:
                        print(f"slideshow download url is None, please check your network.")
                        # self.append_crawled_list(slide_link)
                else:
                    print(f"slideshow does not meet conditions, skip.")
                    self.append_crawled_list(slide_link)
            else:
                print(f"slideshow not allow downloads.")
                self.append_crawled_list(slide_link)
        else:
            print(f"slideshow not in page_props.keys: {page_props}")

        print("-" * 50)

    def slide_filter(self, slide_title, slider_likes):
        if "quiz" not in slide_title.lower() and int(slider_likes) >= 5:
            return True
        else:
            return False

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
        if response["success"]:
            slide_download_url = response["url"]
            print(f"slide download url: {slide_download_url}")
            return slide_download_url
        else:
            print(f"get slide download url fail: {response['error']}")
            return response['error']

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

    def get_popular_payload(self, end_cursor, slide_category_id):
        popular_payload = {
            "query": "\n  query ($after: String, $first: Int, $categoryId: Int, $mediaType: Media!, $period: ListPeriod!, $language: String) {\n    popular(after: $after, first: $first, categoryId: $categoryId, mediaType: $mediaType, period: $period, language: $language) {\n      edges {\n        cursor\n        node {\n          \n  createdAt\n  id\n  canonicalUrl\n  strippedTitle\n  thumbnail\n  title\n  totalSlides\n  type\n  user {\n    id\n    name\n    login\n  }\n  viewCount\n  likeCount\n\n        }\n      }\n      pageInfo {\n        \n  hasNextPage\n  hasPreviousPage\n  startCursor\n  endCursor\n\n      }\n    }\n  }\n",
            "variables": {
                "after": end_cursor,
                "first": 100,  # max value 100
                "categoryId": slide_category_id,
                "mediaType": "PRESENTATIONS",
                "period": "YEAR",
                "language": "en"
            },
            "locale": "en"
        }
        return popular_payload

    def get_latest_payload(self, end_cursor, slide_category_id):
        latest_payload = {
            "query": "\n  query ($after: String, $first: Int, $categoryId: Int, $mediaType: Media!, $language: String) {\n    latest(after: $after, first: $first, categoryId: $categoryId, mediaType: $mediaType, language: $language) {\n      edges {\n        cursor\n        node {\n          \n  createdAt\n  id\n  canonicalUrl\n  strippedTitle\n  thumbnail\n  title\n  totalSlides\n  type\n  user {\n    id\n    name\n    login\n  }\n  viewCount\n  likeCount\n\n        }\n      }\n      pageInfo {\n        \n  hasNextPage\n  hasPreviousPage\n  startCursor\n  endCursor\n\n      }\n    }\n  }\n",
            "variables": {
                "after": end_cursor,
                "first": 100,
                "categoryId": slide_category_id,
                "language": "en",
                "mediaType": "PRESENTATIONS"
            },
            "locale": "en"
        }
        return latest_payload

    def get_featured_payload(self, end_cursor, slide_category_id):
        featured_payload = {
            "query": "\n  query ($after: String, $first: Int, $categoryId: Int, $mediaType: Media!) {\n    featured(after: $after, first: $first, categoryId: $categoryId, mediaType: $mediaType) {\n      edges {\n        cursor\n        node {\n          \n  createdAt\n  id\n  canonicalUrl\n  strippedTitle\n  thumbnail\n  title\n  totalSlides\n  type\n  user {\n    id\n    name\n    login\n  }\n  viewCount\n  likeCount\n\n        }\n      }\n      pageInfo {\n        \n  hasNextPage\n  hasPreviousPage\n  startCursor\n  endCursor\n\n      }\n    }\n  }\n",
            "variables": {
                "after": end_cursor,
                "first": 100,
                "categoryId": slide_category_id,
                "mediaType": "PRESENTATIONS"
            },
            "locale": "en"
        }
        return featured_payload

    def crawl_all_categories(self):
        for slide_category in self.slide_category_list:
            slide_category_url = "https://www.slideshare.net/category/" + slide_category["url"]
            slide_category_id = int(slide_category["id"])
            self.get_category_sub_urls(slide_category_url, slide_category_id)

    def get_category_sub_urls(self, slide_category_url, slide_category_id):
        response = requests.get(slide_category_url, headers=self.headers).text
        soup = BeautifulSoup(response, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        script_string = script_tag.string
        script_json = json.loads(script_string)
        # print(f"script json: {script_json}")
        results = script_json["props"]["pageProps"]["results"]
        for category_type in ["popular", "latest", "featured"]:
            if category_type in results.keys():
                category_type_results = results[category_type]

                for category_type_result in category_type_results["results"]:
                    category_sub_url = category_type_result["canonicalUrl"]
                    if category_sub_url not in self.crawled_url_list:
                        try:
                            print(f"crawl url: {category_sub_url}")
                            self.get_slide_info(category_sub_url)
                        except Exception as e:
                            print(f"crawl error: {str(e)}")
                            if str(e) == "limit of 100 downloads in last 24 hours":
                                print(f"pause 24 hours.")
                                time.sleep(21600)

                category_type_page_info = category_type_results["pageInfo"]
                has_next_page = category_type_page_info["hasNextPage"]
                if has_next_page:
                    end_cursor = category_type_page_info["endCursor"]
                    self.get_category_type_next_slides(category_type, end_cursor, slide_category_id)

    def get_category_type_next_slides(self, category_type, after_cursor, slide_category_id):
        if category_type == "popular":
            payload = self.get_popular_payload(after_cursor, slide_category_id)
        elif category_type == "latest":
            payload = self.get_latest_payload(after_cursor, slide_category_id)
        else:
            payload = self.get_featured_payload(after_cursor, slide_category_id)

        response = requests.post(self.slide_data_api, headers=self.headers, json=payload).text
        json_response = json.loads(response)
        print(f"json response: {json_response}")
        if "data" in json_response.keys():
            category_type_results = json_response["data"][category_type]

            for category_type_result in category_type_results["edges"]:
                category_sub_url = category_type_result["node"]["canonicalUrl"]
                if category_sub_url not in self.crawled_url_list:
                    try:
                        print(f"crawl url: {category_sub_url}")
                        self.get_slide_info(category_sub_url)
                    except Exception as e:
                        print(f"crawl error: {str(e)}")
                        if str(e) == "limit of 100 downloads in last 24 hours":
                            print(f"pause 24 hours.")
                            time.sleep(72000)

            category_type_page_info = category_type_results["pageInfo"]
            has_next_page = category_type_page_info["hasNextPage"]
            if has_next_page:
                end_cursor = category_type_page_info["endCursor"]
                self.get_category_type_next_slides(category_type, end_cursor, slide_category_id)


if __name__ == '__main__':
    sd = SlideDownloader()
    # sd.get_slide_info("https://www.slideshare.net/LilyRay1/googles-just-not-that-into-you-understanding-core-updates-search-intent")
    sd.crawl_all_categories()
