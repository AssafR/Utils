import urllib.request

import requests
import unicodedata
from bs4 import BeautifulSoup
from parse import parse

import sqlite3

snl_eps_url = 'https://epguides.com/saturdaynightlive/'

# Example HTML code:
# <tr><td class='epinfo right'>108.</td><td class='epinfo left pad'>6-2&nbsp;</td><td class='epinfo right pad'>22 Nov 80</td><td class='eptitle left'><a target="_blank" href="https://www.tvmaze.com/episodes/33235/saturday-night-live-6x02-malcolm-mcdowell-captain-beefheart-his-magic-band">Malcolm McDowell / Captain Beefheart &amp; His Magic Band</a></td></tr>


# fp = urllib.request.urlopen(snl_eps_url)
# mybytes = fp.read()
#
# mystr = mybytes.decode("utf8")
# fp.close()
#
# print(mystr)

req = requests.get(snl_eps_url)
soup = BeautifulSoup(req.content, 'html.parser')
# print(soup.prettify())

# tds = soup.find_all("td", class_="bold")
# print("\n".join((td for td in (str(td) for td in tds) if 'Season' in td)))

tds = soup.find_all("td", class_="eptitle left")

attrs_names = {"epinfo left pad": 'ep_number',
               "eptitle left": 'ep_name',
               "epinfo right pad": 'ep_date'}

results = {}

for td in tds:
    episode_name = td.get_text()
    tr = td.parent
    result = {}
    for ep_num in tr.findChildren("td", attrs_names.keys()):  # , _class="epinfo left pad"
        class_name = ' '.join(ep_num['class'])
        text = ep_num.get_text()
        text = unicodedata.normalize("NFKD", text).strip()  # Translate from unicode
        result[attrs_names[class_name]] = text
    ep_num = result['ep_number']
    numbers = parse('{:d}-{:d}', ep_num)
    result['season'] = numbers[0]
    result['ep_in_season'] = numbers[1]
    ep_standard_numbering = f's{numbers[0]:02d}e{numbers[1]:02d}'
    result['ep_standard_numbering'] = ep_standard_numbering
    results[result['ep_standard_numbering']] = result
    # print(result)


# print("\n".join((td for td in (str(td) for td in tds))))

# print(soup.prettify())
# print(results)

def create_insertion_command(value):
    return (
        f'INSERT INTO episodes VALUES\n',
        f'\n',
        f'\n',
        f'\n',
        f'\n',
        f'\n',

    )


con = sqlite3.connect("snl_eps.db")
cur = con.cursor()
cur.execute("""DROP TABLE episodes""")
cur.execute("""CREATE TABLE IF NOT EXISTS episodes(
                    season INTEGER,
                    ep_in_season INTEGER,
                    ep_standard_numbering TEXT PRIMARY KEY,
                    ep_name TEXT,
                    ep_date TEXT)""")

sql_insertion_clause = """
    INSERT INTO episodes (season,ep_in_season,ep_standard_numbering,ep_name, ep_date)
        VALUES(?,?,?,?,?)
    """

# for result in results.values():
#     cur.execute("""
#     INSERT INTO episodes (column1,column2 ,..)
#         VALUES( value1,	value2 ,...)
#     """)

records = [(res['season'], res['ep_in_season'],
            res['ep_standard_numbering'], res['ep_name'],
            res['ep_date']) for res in results.values()]
# print(records)

cur.executemany(sql_insertion_clause, records)
sql_selection_clause = """
    SELECT * FROM episodes
    """

cur.execute(sql_selection_clause)
records_read = cur.fetchall()
print(records_read)