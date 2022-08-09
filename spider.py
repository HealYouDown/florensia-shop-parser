import os
import re
from typing import Optional

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http.response.html import HtmlResponse


def get_id_from_link(link: str) -> int:
    return int(link.rsplit("/", 1)[-1])


def get_id_from_anchor_element(a: scrapy.Selector) -> int:
    return get_id_from_link(a.attrib["href"])


def greedy_parse_integer(s: str) -> int:
    # Replaces any non-digit character in string and
    # interprets it as an integer.
    return int(re.sub(r"\D", "", s))


class Spider(scrapy.Spider):
    name = "FlorensiaShopScrapper"

    def start_requests(self):
        opts = {
            "dont_redirect": True,
            # If added to options, parse will also get 302 responses
            # 'handle_httpstatus_list': [302],
        }

        for i in range(1, 3000):
            yield scrapy.Request(
                url=f"https://www.florensia-online.com/en/shop/detail/index/{i}",
                callback=self.parse,
                meta=opts,
            )

    def parse(self, response: HtmlResponse):
        item_selector: scrapy.Selector = response.xpath("//td[@class='left']")

        id = get_id_from_link(response.url)

        item_name: str = item_selector.xpath("//th[@colspan='3']/text()").get()
        if item_name is None:
            raise Exception("No item name found.")
        item_name = item_name.strip()

        details: list[str] = []
        for details_string in item_selector.xpath("//tr[@class='details']/td/text()").getall():
            # some details have a \n which we can use to split
            details.extend(
                [
                    s.strip()
                    for s in details_string.split("\n")
                    if s.strip() and s.strip() not in [","]
                ]
            )

        variants: dict[str, str | int] = []
        variant_selector: scrapy.Selector
        for variant_selector in item_selector.xpath("//select[@id='product_colors']/option"):
            variants.append(
                {
                    "id": int(variant_selector.attrib.get("value")),
                    "name": variant_selector.xpath("text()").get().strip(),
                }
            )

        timelimit: Optional[str] = item_selector.xpath(
            "//td[@class='timelimit']/following-sibling::td/text()"
        ).get()
        if timelimit is not None:
            timelimit = timelimit.strip()

        prices: list[int] = [
            int(s.split(" AP")[0])
            for s in item_selector.xpath(
                "//td[@class='nobr pprice']/descendant-or-self::*/text()"
            ).getall()
            if s.strip()  # filters out \n
        ]

        description: str = "\n".join(
            [
                s
                for s in item_selector.xpath(
                    "//li[@class='desc']/descendant-or-self::*/text()"
                ).getall()
            ]
        ).strip()

        bundle_ids: list[int] = [
            get_id_from_anchor_element(a) for a in item_selector.xpath("//li[@class='bundle']/a")
        ]

        bundle_items = []
        bundle_item_selector: scrapy.Selector
        for bundle_item_selector in item_selector.xpath("//ul[@class='bundle_items']/li"):
            bundle_items.append(
                {
                    "id": get_id_from_anchor_element(bundle_item_selector.xpath("a")[0]),
                    "amount": greedy_parse_integer(bundle_item_selector.xpath("text()").get()),
                }
            )

        yield {
            "id": id,
            "name": item_name,
            "time_limit": timelimit,
            "details": details,
            "variants": variants,
            "prices": prices,
            "description": description,
            "bundle_ids": bundle_ids,
            "bundle_items": bundle_items,
        }


if __name__ == "__main__":
    FEED_URI = "shop_data.json"
    if os.path.exists(FEED_URI):
        os.remove(FEED_URI)

    process = CrawlerProcess(
        settings={
            "LOG_LEVEL": "INFO",
            "FEED_FORMAT": "json",
            "FEED_URI": FEED_URI,
            "FEED_EXPORT_INDENT": 2,
        }
    )

    process.crawl(Spider)
    process.start()
