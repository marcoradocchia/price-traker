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
from os import listdir,mkdir, rename
from os.path import expanduser, isdir, isfile, join
from re import compile, match, IGNORECASE
from requests import get
from smtplib import SMTP_SSL
from ssl import create_default_context
from sys import argv
from sys import exit as sys_exit
from utils.text import wrap


XDG_CONFIG = expanduser("~/.config/price-traker")
XDG_DATA = expanduser("~/.local/share/price-traker")
CONFIG_FILE = join(XDG_CONFIG, "config")
PRODUCT_LIST_FILE = join(XDG_DATA, "product_list.json")
LOG_FILE = join(XDG_DATA, "traker.log")
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
USERAGENT_FALLBACK = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11\
    (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11"
TIMEOUT = 5

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
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        IGNORECASE,
    )
    if not match(url_regex, url):
        logging.error(f"'{url}' is not a valid URL")
        sys_exit(f"ERROR: '{url}' is not a valid URL")


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
    if 'mail' in config.sections():
        smtp_server = config.get('mail', 'smtp_server')
        # check server url before continue
        check_smtp_server(smtp_server)
        # check mail address before continue
        notifier_addr = config.get('mail', 'notifier_addr')
        check_mail_addr(notifier_addr)
        config_opts['mail'] = {}
        config_opts['mail']['smtp_server'] = smtp_server
        config_opts['mail']['port'] = config.get('mail', 'port')
        config_opts['mail']['notifier_addr'] = notifier_addr
        config_opts['mail']['notifier_psw'] = config.get('mail', 'notifier_psw')
    return config_opts


def get_proxy_list() -> list:
    try:
        response = get(
            'https://free-proxy-list.net/',
            headers={'User-Agent': get_useragent()},
        )
        soup = BeautifulSoup(response.content, 'lxml')
        table = soup.find('tbody')
        proxies = []
        for row in table:
            if row.find_all('td')[4].text =='elite proxy':
                proxy = ':'.join(
                    [row.find_all('td')[0].text,
                    row.find_all('td')[1].text]
                )
                proxies.append(proxy)
        return proxies
    except Exception as e:
        logging.error(f"unable to get proxy list ({e})")
        sys_exit(f"ERROR: unable to get proxy list")


def get_date() -> str:
    return f"{date.today().year}-{date.today().month}-{date.today().day}"


def get_page(url: str) -> BeautifulSoup:
    # use random user agent and rotating proxies to prevent request blocking
    proxy = get_working_proxy()
    try:
        page = BeautifulSoup(
            get(
                url=url,
                headers={'User-Agent': get_useragent()},
                proxies={
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}',
                },
                timeout=TIMEOUT,
            ).text,
            'lxml'
        )
    except Exception as e:
        logging.error(f"unable to load page '{url}' ({e})")
        sys_exit(f"ERROR: unable to load page '{url}'")
    return page


def get_price(page: BeautifulSoup) -> float:
    try:
        price = page.find(class_='a-offscreen') # this is for amazon only atm
        price = float(price.text.strip('\n')[:-1].replace(',', '.'))
        return price
    except Exception as e:
        logging.error(f"unable to retrieve price information in page ({e})")
        sys_exit(f"ERROR: unable to retrieve price information in page")


def get_working_proxy(proxy_list: list) -> str:
    while len(proxy_list) > 0:
        proxy = proxy_list.pop()
        proxy_ip = proxy.split(':')[0]
        try:
            response = get(
                url='https://httpbin.org/ip',
                proxies={
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}',
                },
                timeout=TIMEOUT,
            ).json()
            if response['origin'] == proxy_ip:
                return proxy
        except:
            pass
    logging.error("unable to find working proxy")
    sys_exit("ERROR: unable to find working proxy")

def get_useragent() -> str:
    """
    Return random useragent string using fake_useragent library for anonimity
    and to prevent blocked requests.
    Update UserAgent's cache monthly:
    look for ~/.local/share/useragents_<month>.json: if exists and <month>
    correspond to current month then use that cache, otherwhise rename file
    to current month and upadte UserAgent cache.
    """
    xdg_data_files = listdir(XDG_DATA)
    need_cache_update = True
    useragents_file = join(
        XDG_DATA,
        'useragents_' + str(date.today().month) + '.json'
    )
    for file in xdg_data_files:
        if "useragents" in file:
            if int(file.split('.json')[0][-2:]) == date.today().month:
                need_cache_update = False
            else:
                rename(join(XDG_DATA, file), useragents_file)
            break
    ua = UserAgent(
        fallback=USERAGENT_FALLBACK,
        path=useragents_file
    )
    # update user agent cache every month
    if need_cache_update:
        ua.update()
        logging.warning("updated UserAgent cache")
    return ua.random


# FILE READING/WRITING
def write_list(products: list) -> None:
    with open(PRODUCT_LIST_FILE, 'w+') as products_file:
        products_file.write(json_dumps(products, indent=4))


def get_list() -> list:
    # check for data file
    if not isfile(PRODUCT_LIST_FILE):
        # check for data directory, if doesn't exist try to create one
        if not isdir(XDG_DATA):
            try:
                mkdir(XDG_DATA)
            except Exception as e:
                logging.error(f"unable to create directory {XDG_DATA} ({e})")
                sys_exit(f"ERROR: unable to create directory {XDG_DATA}")
        write_list(products=[])
        return [] # if file didn't exist, no need to read it
    with open(PRODUCT_LIST_FILE, 'r') as products_file:
        product_list = json_loads(products_file.read())
    return product_list


# NOTIFICATIONS
def send_notification(mail_addr: str, mail_body: str) -> None:
    config_opts = get_config()
    if 'mail' in config_opts:
        mail = EmailMessage()
        mail['Subject'] = "Price Traker: lower price detected"
        mail['To'] = mail_addr
        mail['From'] = config_opts['mail']['notifier_addr']
        mail.set_content(mail_body)
        try:
            with SMTP_SSL(
                config_opts['mail']['smtp_server'],
                config_opts['mail']['port'],
                context=create_default_context(),
            ) as server:
                server.login(
                    config_opts['mail']['notifier_addr'],
                    config_opts['mail']['notifier_psw'],
                )
                server.send_message(mail)
                logging.info(f"mail notification sent to {mail_addr}")
        except Exception as e:
            logging.error(
                "unable to send mail notification "
                f"to '{mail_addr}' ({e})"
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
        if (product['url'] == url):
            if mail_addr in product['followers']:
                warning_msg = (
                    f"'{mail_addr}' already tracking "
                    f"'{product['url']}...'"
                )
                logging.warning(warning_msg)
                # if mail_addr already in followers array, exit
                sys_exit( f"WARNING: {warning_msg}")
            else:
                # product already in product_list but mail_addr not in followers
                # add mail_addr to followers and exit
                product['followers'].append(mail_addr)
                logging.info(
                    f"'{mail_addr}' started tracking "
                    f"'{product['title']}' "
                    f"({product['url']})"
                )
                write_list(products=product_list)
                return
    # if product not found in product_list, add new entry to product_list
    page = get_page(url=url)
    try:
        title = page.find(id='productTitle').text.strip(' \n') # TODO amazon only atm
    except Exception as e:
        logging.error(f"no id found at given url page ({e})")
        sys_exit(f"ERROR: no id found at given url page")
    product_list.append(
        {
            'url': url,
            'title': title,
            'followers': [mail_addr],
            'prices': [
                {
                    'date': get_date(),
                    'price': get_price(page)
                }
            ],
        }
    )
    logging.info(
        f"'{mail_addr}' started tracking "
        f"'{title}' "
        f"({url})"
    )
    # write updated product_list to PRODUCT_LIST_FILE
    write_list(products=product_list)


def list_products() -> None:
    product_list = get_list()
    for product in product_list:
        print(
            f"├─ {wrap(input=product['title'])}\n"
            f"│  ├── {product['prices'][-1]['price']}€\n"
            f"│  ├── {product['prices'][-1]['date']}\n"
            f"│  └── {wrap(input=', '.join(product['followers']), prefix_length=7)}\n"
        ) 


def remove_product(substr: str, mail_addr: str) -> None:
    # check for valid mail address before continuing
    check_mail_addr(mail_addr)
    product_list = get_list()
    for product in product_list:
        if substr.lower() in product['title'].lower():
            if mail_addr not in product['followers']:
                return
            if input(
                    f"Remove '{mail_addr}' from "
                    f"'{product['title']}' followers list? [y/N]: "
                ).lower() == 'y':
                product['followers'].remove(mail_addr)
                write_list(products=product_list)
                logging.info(
                    f"'{mail_addr}' stopped tracking "
                    f"'{product['title']}' "
                    f"({product['url']})"
                )
        else:
            logging.warning(f"no tracked product matching query '{substr}'")
            sys_exit(f"WARNING: no tracked product matching query '{substr}'")


def update_prices() -> None:
    product_list = get_list()
    today = get_date()
    # exit on empty product_list
    if len(product_list) == 0:
        logging.warning("update request with empty product list")
        sys_exit("WARNING: no products tracking list")
    # notification_queue object structure:
    # {
    #   'mail_addr1': 'mail_body1',
    #   'mail_addr2': 'mail_body2',
    # }
    notification_queue = {}
    for product in product_list:
        # if the last price update is today,
        # ignore updating price for that product
        if product['prices'][-1]['date'] == today:
            continue
        page = get_page(url=product['url'])
        today_price = get_price(page)
        product['prices'].append(
            {
                'date': today,
                'price': today_price
            }
        )
        prev_price = product['prices'][-2]['price']
        price_delta = round(today_price - prev_price, 2)
        # if product has lower price than last check,
        # add followers to notification_queue
        if price_delta < 0:
            notification_body = (
                f"├─ {wrap(input=product['title'], prefix_length=3)}\n"
                f"│   ├── url: {wrap(input=product['url'], prefix_length=13)}\n"
                f"│   ├── previous price: {prev_price}€ "
                f"({product['prices'][-2]['date']})\n"
                f"│   ├── current price: {today_price}€ ({today})\n"
                f"│   └── delta: {price_delta}€\n"
            )
            # for each follower of the product, append the notification_body
            # if it already exists in the notification_queue,
            # create an instance otherwhise
            for follower in product['followers']:
                if follower in notification_queue:
                    notification_queue[follower] += notification_body
                else:
                    notification_queue[follower] = notification_body
    # write updated product_list to PRODUCT_LIST_FILE
    write_list(products=product_list)
    # mail
    for mail_addr in notification_queue:
        send_notification(
            mail_addr=mail_addr,
            mail_body=notification_queue[mail_addr],
        )


# MAIN
def main() -> None:
    # configuring logging
    logging.basicConfig(
        filename=LOG_FILE,
        encoding='utf-8',
        format=LOG_FORMAT,
        datefmt='%Y-%m-%d [%H:%M:%S]',
        level=20, # INFO level
    )

    # TODO format usage
    argparser = ArgumentParser(allow_abbrev=False)
    argparser.add_argument(
        '-i', '--insert',
        type=str,
        nargs=2,
        metavar=('<url>', '<mail>'),
        help= (
            '<mail> starts tracking <url> '
            '(requires valid mail option for noticitation purposes)'
        )
    )
    argparser.add_argument(
        '-l', '--list',
        action='store_true',
        help='list all the tracked products'
    )
    argparser.add_argument(
        '-r', '--remove',
        type=str,
        nargs=2,
        metavar=('<title_substr>', '<mail>'),
        help= (
            '<mail> stops tracking <title_substr> '
            '(<title_substr> indicates a substring of the product title)'
        )
    )
    argparser.add_argument(
        '-u', '--update',
        action='store_true',
        help='update prices for every product'
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


if __name__ == '__main__':
    main()
