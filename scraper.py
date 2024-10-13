import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse, parse_qs
import string
from confluent_kafka import Producer
import json
import logging

logging.basicConfig(level=logging.INFO)

conf = {'bootstrap.servers': 'localhost:8097'}
producer = Producer(**conf)

baseurl = "https://www.1mg.com"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

def fetch_product_links(letter, page_number):
    url = f'{baseurl}/drugs-all-medicines?page={page_number}&label={letter}'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    
    productlinks = []
    productlist = soup.find_all('div', class_='Card__container__liTc5 Card__productCard__SrdLF Card__direction__H8OmP container-fluid-padded-xl')
    
    for item in productlist:
        for link in item.find_all('a', href=True):
            productlinks.append(baseurl + link['href'])
    
    return productlinks, soup

def find_next_page(soup):
    pagination_buttons = soup.find_all('div', class_='AllMedicines__paginationButton__QmWCn marginBoth-16 col-3')
    for button in pagination_buttons:
        a_tag = button.find('a', href=True)
        text = a_tag.text if a_tag else None
        if a_tag and text == 'Next':
            href = a_tag.get('href', '')
            parsed_url = urlparse(href)
            query_parameters = parse_qs(parsed_url.query)
            return query_parameters.get('page', [None])[0]
    return None

def fetch_medicine_data(link):
    try:
        r = requests.get(link, headers=headers, timeout=90)
        r.raise_for_status()
    except requests.exceptions.RequestException as err:
        logging.error(f"Error fetching {link}: {err}")
        return None
    
    soup = BeautifulSoup(r.content, 'html.parser')

    name = soup.find('h1', class_='DrugHeader__title-content___2ZaPo')
    name = name.text.strip() if name else link

    composition = soup.find('div', class_='saltInfo DrugHeader__meta-value___vqYM0')
    composition = composition.text.strip() if composition else None

    useslist = soup.find_all('ul', class_='DrugOverview__list___1HjxR DrugOverview__uses___1jmC3')
    uses = [a_tag.text.strip() for uses in useslist for a_tag in uses.find_all('li')]

    sideeffects = soup.find_all('div', class_='DrugOverview__list-container___2eAr6 DrugOverview__content___22ZBX')
    side_effects = [li_tag.text.strip() for se in sideeffects for li_tag in se.find_all('li')]

    return {'name': name, 'composition': composition, 'uses': uses, 'side effects': side_effects}

def process_letter(letter):
    medlist = []
    med_unfetched = []
    page_number = 1
    productlinks = []

    logging.info(f'Processing letter: {letter}')
    
    while True:
        new_links, soup = fetch_product_links(letter, page_number)
        productlinks.extend(new_links)

        page_number = find_next_page(soup)
        if not page_number:
            break

    for i, link in enumerate(productlinks, start=1):
        medicine = fetch_medicine_data(link)
        if medicine:
            medlist.append(medicine)
            try:
                
                producer.produce('randomTopic', value=json.dumps(medicine), callback=delivery_report)
               
                producer.flush()  
                logging.info(f'Saved to Kafka: {medicine["name"]} >> {i}')
            except Exception as e:
                logging.error(f'Failed to send {medicine["name"]} to Kafka: {e}')
        else:
            med_unfetched.append(link)
        time.sleep(1)

    return medlist, med_unfetched

def delivery_report(err, msg):
    """ Callback for delivery reports. """
    if err is not None:
        logging.error(f'Failed to send {msg.key() if msg.key() else "message"} to Kafka: {err}')
    else:
        logging.info(f'Successfully sent message to Kafka: {str(msg)}')

def main():
    start_letter = 'a'
    end_letter = 'z'

    for letter in [l for l in string.ascii_lowercase if start_letter <= l <= end_letter]:
        medlist, med_unfetched = process_letter(letter)
        logging.info(f"Finished processing {letter}. Fetched {len(medlist)} medicines, {len(med_unfetched)} unfetched.")

if __name__ == "__main__":
    main()
