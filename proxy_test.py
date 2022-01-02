from bs4 import BeautifulSoup
from requests import get

# def get_proxy_list() -> list:
#     url=
def get_proxies() -> list:
    response = get('https://free-proxy-list.net/')
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

def random_proxy(proxy_list: list) -> str:
    return proxy_list.pop()

def main() -> None:
    proxy_list = get_proxies()
    counter = 0
    while len(proxy_list) > 0:
        proxy = random_proxy(proxy_list=proxy_list)
        proxy_ip = proxy.split(':')[0]
        try:
            response = get(
                url='https://httpbin.org/ip',
                proxies={
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}',
                },
                timeout=5,
            ).json()
            if response['origin'] == proxy_ip:
                print(proxy_ip + " -- working")
                counter += 1
        except Exception:
            print(proxy_ip + " -- not working")
    print(counter)

if __name__ == "__main__":
    main()
