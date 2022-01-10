# Price Traker: price tracking tool
This is a simple tool to track lowering prices of products on various
websites[1].
The idea behind this tool is to create a tracking list, in order to check for
the product list items' prices periodically, using fake useragents and rotating
proxies for anonimity and preventing sites to block http requests.

## Dependencies
The tool has very minimal dependencies, considering that it uses Python's
integrated libraries for most of the work:
- `beautifulsoup4`;
- `fake-useragent`;
- `lxml` (as BeautifulSoup documentation recommends it for speed);

Both can be installed via `pip install beautifulsoup4 lxml fake-useragent`.

### Arch packages
For **Arch Linux** users packages are available in the standard repos, hence
for installation using pacman: `# pacman -S python-beautifulsoup4 python-lxml`.
For the `fake-useragent` dependency **AUR** package available, the installation
with an aur-helper such as `yay`: `$ yay -S python-fake-useragent`.

## Configuration
_Work in progress..._

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

In order to add a new product to the tracking list use the `-i, --insert`
option with the first argument being the product's URL and the second the
e-mail for notifications.

In order to remove a product from the from the tracking list use the `-r,
--remove` option with the only argument being a _prefix_ of the product's
name.

Update option `-u, --update` updates product list items' prices and notifies
via e-mail about the products with lowering prices.

In order to know what products are being tracked and list them use `-l, --list`
option.

^[1] Currently only _Amazon_ supported
