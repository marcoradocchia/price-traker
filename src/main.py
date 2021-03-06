#!/usr/bin/env python3
# coding=utf-8

import logging
from argparse import ArgumentParser
from bs4 import BeautifulSoup
from configparser import ConfigParser
from datetime import date
from email.message import EmailMessage
from fake_useragent import UserAgent
from json import dumps as json_dumps
from json import loads as json_loads
from os import listdir, mkdir, rename
from os.path import expanduser, isdir, isfile, join
from random import choice
from re import compile, match, IGNORECASE
from requests import get
from smtplib import SMTP_SSL
from ssl import create_default_context
from sys import argv
from sys import exit as sys_exit
from time import sleep


XDG_CONFIG = expanduser("~/.config/price-traker")
XDG_DATA = expanduser("~/.local/share/price-traker")
CONFIG_FILE = join(XDG_CONFIG, "config")
PRODUCT_LIST_FILE = join(XDG_DATA, "product_list.json")
LOG_FILE = join(XDG_DATA, "traker.log")
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
USERAGENT_FALLBACK = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11"
    "(KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11"
)
PROXY_LIST_API_URL = (
    "https://proxylist.geonode.com/api/proxy-list?"
    "limit=50&page=1&sort_by=lastChecked&sort_type="
    "desc&anonymityLevel=elite&anonymityLevel=anonymous"
)
TIMEOUT = 5
MAX_RETRIES = 3


# UTILS
def check_mail_addr(mail: str) -> None:
    if not match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", mail):
        logging.error(f"'{mail}' is not a valid mail address")
        sys_exit(f"ERROR: '{mail}' is not a valid mail address")


def check_smtp_server(server_url: str) -> None:
    if not match(r"^[A-Za-z0-9\.\+_-]+\.[a-zA-Z]*$", server_url):
        logging.error(f"{server_url} is not a valid SMTP server URL")
        sys_exit(f"ERROR: '{server_url}' is not a valid SMTP server URL")


def check_url(url: str) -> None:
    url_regex = compile(
        r"^(?:http|ftp)s?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)"
        r"+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        IGNORECASE,
    )
    if not match(url_regex, url):
        logging.error(f"'{url}' is not a valid URL")
        sys_exit(f"ERROR: '{url}' is not a valid URL")


def get_brute(proxies: list, url: str, retries: int = 0) -> dict:
    """
    random user agent and rotating proxies to prevent request blocking
    try to get page while proxies are available
    (this loop prevents breaking in case a proxy is actually working but
    gets blocked by the service)
    """
    if retries >= MAX_RETRIES:
        logging.error("max retries reached, impossible to retrieve infos")
        sys_exit("ERROR: max retries reached, impossible to retrieve infos")
    infos = {
        "title": None,
        "price": None,
    }
    while len(proxies) > 0:
        proxy = get_working_proxy(proxy_list=proxies)
        print(f"{len(proxies)} available proxies remaining")
        try:
            page = get_page(url=url, proxy=proxy)
            infos["price"] = get_price(page)
            infos["title"] = page.find(id="productTitle").text.strip(" \n")
            proxies.remove(proxy)  # remove used proxy from proxy list
            break
        except Exception as e:
            logging.error(f"proxy {proxy} failed ({e})")
            continue
    # proxy list got empty before non-blocked ones could be found
    if len(proxies) <= 0:
        # if no working proxy was found or every working proxy was blocked
        # then sleep 10 minutes until new proxy list is available
        # then recursively run this function
        print(
            "every proxy in list was not working or got blocked, waiting 10"
            "minutes for next retry"
        )
        sleep(600)
        get_brute(proxies=get_proxy_list(), url=url, retries=retries + 1)
    return infos


def get_config() -> dict:
    # check for configuration file, if not found then exit
    if not isfile(CONFIG_FILE):
        logging.error("configuration file not found")
        sys_exit(
            "ERROR: Configuration file not found."
            f"please create configuration file at {CONFIG_FILE}"
        )
    config = ConfigParser()
    config.read(CONFIG_FILE)
    config_opts = {}
    if "mail" in config.sections():
        smtp_server = config.get("mail", "smtp_server")
        # check server url before continue
        check_smtp_server(smtp_server)
        # check mail address before continue
        notifier_addr = config.get("mail", "notifier_addr")
        check_mail_addr(notifier_addr)
        config_opts["mail"] = {}
        config_opts["mail"]["smtp_server"] = smtp_server
        config_opts["mail"]["port"] = config.get("mail", "port")
        config_opts["mail"]["notifier_addr"] = notifier_addr
        config_opts["mail"]["notifier_psw"] = config.get(
            "mail", "notifier_psw"
        )
    return config_opts


def get_proxy_list() -> list:
    print("Retrieving proxy list...")
    try:
        proxies = []
        response = get(
            PROXY_LIST_API_URL,
            headers={"User-Agent": get_useragent()},
        ).json()
        print(f"{response['total']} proxies found")
        for proxy in response["data"]:
            proxies.append(f"{proxy['ip']}:{proxy['port']}")
        return proxies
    except Exception as e:
        logging.error(f"unable to get proxy list ({e})")
        sys_exit("ERROR: unable to get proxy list")


def get_date() -> str:
    return str(date.today())


def get_page(url: str, proxy: str) -> BeautifulSoup:
    print("Contacting server...")
    page = get(
        url=url,
        headers={"User-Agent": get_useragent()},
        proxies={
            "http": f"http://{proxy}",
            "https": f"http://{proxy}",
        },
        timeout=60,
    ).text
    page = BeautifulSoup(page, "lxml")
    return page


def get_price(page: BeautifulSoup) -> float:
    price = page.find(class_="a-offscreen")  # this is for AMAZON only atm
    price = float(price.text.strip("\n")[:-1].replace(",", "."))
    return price


def get_working_proxy(proxy_list: list) -> str:
    """
    Looking for working proxy requesting httpbin.org/ip which returns a
    json containing the ip: if ip matches, then return <proxy_ip>:<port>
    as a string
    """
    print("Looking for working proxy...")
    while len(proxy_list) > 0:
        proxy = choice(proxy_list)  # select random proxy from list
        proxy_ip = proxy.split(":")[0]
        try:
            response = get(
                url="https://httpbin.org/ip",
                proxies={
                    "http": f"http://{proxy}",
                    "https": f"http://{proxy}",
                },
                timeout=TIMEOUT,
            ).json()
            if response["origin"] == proxy_ip:
                logging.info(f"using proxy {proxy_ip}")
                print(f"Using proxy: {proxy_ip}")
                return proxy
        except Exception:
            # remove not working proxy from list
            proxy_list.remove(proxy)
    logging.error("unable to find working proxy")
    sys_exit("ERROR: unable to find working proxy")


def get_useragent() -> str:
    """
    Return random useragent string using fake_useragent library for
    anonimity and to prevent blocked requests. Update UserAgent's cache
    monthly: look for ~/.local/share/useragents_<month>.json: if exists and
    <month> correspond to current month then use that cache, otherwhise
    rename file to current month and upadte UserAgent cache.
    """
    xdg_data_files = listdir(XDG_DATA)
    need_cache_update = True
    useragents_file = join(
        XDG_DATA, "useragents_" + str(date.today().month) + ".json"
    )
    for file in xdg_data_files:
        if "useragents" in file:
            if int(file.split(".json")[0].split("_")[1]) == date.today().month:
                need_cache_update = False
            else:
                rename(join(XDG_DATA, file), useragents_file)
            break
    ua = UserAgent(fallback=USERAGENT_FALLBACK, path=useragents_file)
    # update user agent cache every month
    if need_cache_update:
        ua.update()
        logging.warning("updated UserAgent cache")
    return ua.random


# FILE READING/WRITING
def check_data_dir() -> None:
    # check for data directory, if doesn't exist try to create one
    if not isdir(XDG_DATA):
        try:
            mkdir(XDG_DATA)
        except Exception as e:
            logging.error(f"unable to create directory {XDG_DATA} ({e})")
            sys_exit(f"ERROR: unable to create directory {XDG_DATA}")


def write_list(products: list) -> None:
    with open(PRODUCT_LIST_FILE, "w+") as products_file:
        products_file.write(json_dumps(products, indent=2))


def get_list() -> list:
    # check for data file
    if not isfile(PRODUCT_LIST_FILE):
        check_data_dir()
        write_list(products=[])
        return []  # if file didn't exist, no need to read it
    with open(PRODUCT_LIST_FILE, "r") as products_file:
        product_list = json_loads(products_file.read())
    return product_list


# NOTIFICATIONS
def send_notification(mail_addr: str, mail_body: str) -> None:
    print(f"Sending mail notification to {mail_addr}")
    config_opts = get_config()
    if "mail" in config_opts:
        mail = EmailMessage()
        mail["Subject"] = "Price Traker: lower price detected"
        mail["To"] = mail_addr
        mail["From"] = config_opts["mail"]["notifier_addr"]
        mail.set_content(mail_body)
        try:
            with SMTP_SSL(
                config_opts["mail"]["smtp_server"],
                config_opts["mail"]["port"],
                context=create_default_context(),
            ) as server:
                server.login(
                    config_opts["mail"]["notifier_addr"],
                    config_opts["mail"]["notifier_psw"],
                )
                server.send_message(mail)
                logging.info(f"mail notification sent to {mail_addr}")
        except Exception as e:
            logging.error(
                "unable to send mail notification " f"to '{mail_addr}' ({e})"
            )
            print(f"unable to send mail notification to '{mail_addr}'")


# FEATURES
def insert_product(url: str, mail_addr: str) -> None:
    # check for valid url and mail address before continuing
    check_url(url)
    check_mail_addr(mail_addr)
    product_list = get_list()
    # look for product in product_list
    for product in product_list:
        if product["url"] == url:
            if mail_addr in product["followers"]:
                warning_msg = (
                    f"'{mail_addr}' already tracking " f"'{product['url']}...'"
                )
                logging.warning(warning_msg)
                # if mail_addr already in followers array, exit
                sys_exit(f"WARNING: {warning_msg}")
            else:
                # product already in product_list but mail_addr not in
                # followers so add mail_addr to followers and exit
                product["followers"].append(mail_addr)
                title = product["title"]
                write_list(products=product_list)
                logging.info(
                    f"'{mail_addr}' started tracking '{title}' " f"({url})"
                )
                sys_exit(
                    f"'{mail_addr}' started tracking '{title}' " f"({url})"
                )
    # if product not found in product_list, add new entry to product_list
    # get_brute function may take a while since it retries util every price
    # it's retrieved
    proxies = get_proxy_list()
    infos = get_brute(proxies=proxies, url=url)
    product_list.append(
        {
            "url": url,
            "title": infos["title"],
            "followers": [mail_addr],
            "prices": [{"date": get_date(), "price": infos["price"]}],
        }
    )
    # write updated product_list to PRODUCT_LIST_FILE
    write_list(products=product_list)
    logging.info(
        f"'{mail_addr}' started tracking '{infos['title']}' " f"({url})"
    )
    sys_exit(
        f"'{mail_addr}' started tracking '{infos['title']}' "
        f"({url})\n"
        "Done"
    )


def list_products() -> None:
    product_list = get_list()
    for product in product_list:
        print(
            f"?????? {product['title'][:50]}...\n"
            f"???  ????????? {product['prices'][-1]['price']}???\n"
            f"???  ????????? {product['prices'][-1]['date']}\n"
            f"???  ????????? {', '.join(product['followers'])}"
        )


def remove_product(substr: str, mail_addr: str) -> None:
    # check for valid mail address before continuing
    check_mail_addr(mail_addr)
    product_list = get_list()
    for product in product_list:
        if substr.lower() in product["title"].lower():
            if mail_addr not in product["followers"]:
                not_tracking_msg = (
                    f"'{mail_addr}' is not tracking '{product['url']}'"
                )
                logging.error(not_tracking_msg)
                sys_exit("ERROR: " + not_tracking_msg)
            confirm_msg = (
                f"Remove '{mail_addr}' from "
                f"'{product['title']}' followers list? [y/N]: "
            )
            if input(confirm_msg).lower() == "y":
                if len(product["followers"]) > 1:
                    product["followers"].remove(mail_addr)
                    info_msg = (
                        f"'{mail_addr}' stopped tracking "
                        f"'{product['title']}' "
                        f"({product['url']})"
                    )
                    logging.info(info_msg)
                    print(info_msg)
                else:
                    product_list.remove(product)
                    info_msg = (
                        f"'{product['title']}' ({product['url']}) removed"
                    )
                    logging.info(info_msg)
                    print(info_msg)
                write_list(products=product_list)
            break
        else:
            warning_msg = f"no tracked product matching query '{substr}'"
            logging.warning(warning_msg)
            sys_exit("WARNING: " + warning_msg)


def update_prices() -> None:
    # list of product whose price is not up to date and needs to be updated
    product_list = []
    today = get_date()
    for product in get_list():
        # if the last price update is today,
        # ignore updating price for that product
        if product["prices"][-1]["date"] == today:
            print(f"{product['title'][:50]} price up to date")
            continue
        else:
            product_list.append(product)
    if len(product_list) == 0:
        sys_exit("Done")
    proxies = get_proxy_list()
    print(f"{len(proxies)} proxies found")
    # exit on empty product_list
    if len(product_list) == 0:
        logging.warning("update request with empty product list")
        sys_exit("WARNING: no products tracking list")
    notification_queue = {}
    # notification_queue object structure:
    # {
    #   'mail_addr1': 'mail_body1',
    #   'mail_addr2': 'mail_body2',
    # }
    for product in product_list:
        # get_brute function may take a while since it retries util every price
        # it's retrieved
        infos = get_brute(proxies=proxies, url=product["url"])
        # checking if the product title
        # corresponds to the one we are looking for
        if infos["title"] != product["title"]:
            logging.warning(
                f"{product['url']} does not correspond to given product"
                "title... skipping"
            )
            print(
                f"{product['url']} does not correspond to given product"
                "title... skipping"
            )
            continue
        today_price = infos["price"]
        product["prices"].append({"date": today, "price": today_price})
        prev_price = product["prices"][-2]["price"]
        price_delta = round(today_price - prev_price, 2)
        # if product has lower price than last check,
        # add followers to notification_queue
        if price_delta < 0:
            notification_body = (
                f"?????? {product['title']}\n"
                f"???   ????????? url: {product['url']}\n"
                f"???   ????????? previous price: {prev_price}??? "
                f"({product['prices'][-2]['date']})\n"
                f"???   ????????? current price: {today_price}??? ({today})\n"
                f"???   ????????? delta: {price_delta}???\n"
            )
            # for each follower of the product, append the notification_body
            # if it already exists in the notification_queue,
            # create an instance otherwhise
            for follower in product["followers"]:
                if follower in notification_queue:
                    notification_queue[follower] += notification_body
                else:
                    notification_queue[follower] = notification_body
    # write updated product_list to PRODUCT_LIST_FILE
    write_list(products=product_list)
    if len(notification_queue) == 0:
        logging.info("No lower prices detected")
        sys_exit("No lower prices detected\nDone")
    print("Sending e-mail notifications...")
    # mail
    for mail_addr in notification_queue:
        send_notification(
            mail_addr=mail_addr,
            mail_body=notification_queue[mail_addr],
        )
    print("Done")


# MAIN
def main() -> None:
    # if log file doesn't exist, create it
    if not isfile(LOG_FILE):
        check_data_dir()  # check if data directory exists
        with open(LOG_FILE, "w+") as logfile:
            logfile.writelines(["-- PRICE TRAKER LOG --\n"])
    # configuring logging
    logging.basicConfig(
        filename=LOG_FILE,
        encoding="utf-8",
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d [%H:%M:%S]",
        level=20,  # INFO level
    )
    argparser = ArgumentParser(allow_abbrev=False)
    argparser.add_argument(
        "-i",
        "--insert",
        type=str,
        nargs=2,
        metavar=("<url>", "<mail>"),
        help=(
            "<mail> starts tracking <url> "
            "(requires valid mail option for noticitation purposes)"
        ),
    )
    argparser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list all the tracked products",
    )
    argparser.add_argument(
        "-r",
        "--remove",
        type=str,
        nargs=2,
        metavar=("<title_substr>", "<mail>"),
        help=(
            "<mail> stops tracking <title_substr> "
            "(<title_substr> indicates a substring of the product title)"
        ),
    )
    argparser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="update prices for every product",
    )

    if len(argv) == 1:  # If no argument is given print help and exit
        argparser.print_help()
        argparser.exit(status=0)
    args = argparser.parse_args()
    if args.remove is not None:
        remove_product(args.remove[0], args.remove[1])
    if args.insert is not None:
        insert_product(url=args.insert[0], mail_addr=args.insert[1])
    if args.update:
        update_prices()
    if args.list:
        list_products()


if __name__ == "__main__":
    main()
