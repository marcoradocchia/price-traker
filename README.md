# Price Traker: price tracking tool
This is a simple tool to track lowering prices of products on various
websites[^1].
The idea behind this tool is to create a tracking list, in order to check for
the product list items' prices periodically[^2], using fake useragents and
rotating proxies for anonimity and preventing sites to block http requests.

## Dependencies
The tool has very minimal dependencies, considering that it uses Python's
integrated libraries for most of the work:
- `beautifulsoup4`;
- `fake-useragent`;
- `lxml` (as BeautifulSoup documentation recommends it for speed);
these be installed via `pip install beautifulsoup4 lxml fake-useragent`.

### Arch packages
For **Arch Linux** users packages are available in the standard repos, hence
for installation using pacman: `# pacman -S python-beautifulsoup4 python-lxml`.
For the `fake-useragent` dependency **AUR** package available, the installation
with an aur-helper such as `yay`: `$ yay -S python-fake-useragent`.

## Configuration
Configuration file needs to be created manually and located at
`~/.config/price-traker/config`.
The tool manages configuration using python's `configparser` library, which
requires INI file structure as stated in the library's
[documentation](https://docs.python.org/3/library/configparser.html#supported-ini-file-structure).

The `[mail]` section is required, as well as the options illustrated in the
example configuration below, where the angled brackets placeholder need to be
replaced with actual values.
```
[mail]
smtp_server = <smtp_server>
port = <smtp_port>
notifier_addr = <email_address>
notifier_psw = <email_password>
```
## Log and Data
Log and data files are stored locally at `~/.local/share/price-traker/`, which
is auto-generated if not present.
The directory will contain:
- `product_list.json`;
- `traker.log`;
- `useragents_{1..12}.json` (file autoupdated every month containing fake-useragent data).

## Usage
```
usage: traker [-h] [-i <url> <mail>] [-l] [-r <title_substr> <mail>] [-u]

options:
  -h, --help            show this help message and exit
  -i <url> <mail>, --insert <url> <mail>
                        <mail> starts tracking <url> (requires valid mail
                        option for noticitation purposes)
  -l, --list            list all the tracked products
  -r <title_substr> <mail>, --remove <title_substr> <mail>
                        <mail> stops tracking <title_substr> (<title_substr>
                        indicates a substring of the product title)
  -u, --update          update prices for every product
```
| Flag | Description |
| :---: | :--- |
| `-i`, `--insert` | **Add** new product to the tracking list; `<url>` represents the tracked product's url, while `<mail>` the address receiving notifications on lowering price |
| `-r`, `--remove` | **Remove** product from the tracking list; `<mail>` represents the user willing to stop tracking some product and `<title_substr>` represents some title's substring of the product |
| `-u`, `--update` | **Updates** all tracked products' prices and notifies via e-mail about the products with lowering prices |
| `-l`, `--list` | **List** all tracked product and corresponding product followers |

[^1]: Currently only _Amazon_ supported
[^2]: e.g. running a cronjob on a Raspberry Pi
