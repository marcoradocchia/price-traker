# Price Traker: price tracking tool
This is a simple tool to track price changes of product on various websites.
The idea behind this tool is to create a tracking list, in order to check for
the product list items' prices periodically.

## Dependencies
The tool has very minimal dependencies, considering that it uses Python's
integrated libraries for most of the work:
- `beautifulsoup4`;
- `lxml` (as BeautifulSoup documentation recommends it for speed).
Both can be installed via `pip install beautifulsoup4 lxml`.

For **Arch Linux** users packages are available in the standard repos, hence
for installation using pacman: `# pacman -S python-beautifulsoup4 python-lxml`.

## Configuration

## Usage
```sh
usage: traker [-h] [-u] [-i INSERT INSERT] [-r REMOVE] [-l]

options:
  -h, --help            show this help message and exit
  -u, --update          update prices for every product
  -i INSERT INSERT, --insert INSERT INSERT
                        insert new product to the traking list given product
                        URL and notification mail address
  -r REMOVE, --remove REMOVE
                        remove product from the traking list
  -l, --list            list all the tracked products
```

In order to add a new product to the tracking list use the `-i, --insert`
option with the first argument being the product's URL and the second the
e-mail to notify to.

In order to remove a product from the from the tracking list use the `-r,
--remove` option with the only argument being a _prefix_ of the product's
name.

Update option `-u, --update` updates product list items' prices and notifies
via e-mail about the products with lower prices than last check.

In order to know what products are being tracked use `-l, --list` option.
