import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import xml.etree.ElementTree as ET
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

def get_data_from_justetf(isin):
    try:
        # Configurazione di Selenium per ottenere il DOM iniziale
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Modalità senza GUI
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=chrome_options)
        url = f"https://www.justetf.com/en/etf-profile.html?isin={isin}"
        driver.get(url)

        # Recupera i cookies
        cookies = driver.get_cookies()

        # Recupera il contenuto della pagina iniziale
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        # Estrazione del nome dell'ETF
        name = soup.find("h1", {"id": "etf-title"}).text.strip()

        # Trova tutti i tag <script>
        script_tags = soup.find_all('script')

        # Cerca "loadMoreSectors" e "loadMoreCountries" all'interno del contenuto dei tag <script>
        countries_found = False
        sector_found = False  # Flag per verificare se la stringa è stata trovata
        for script in script_tags:
            if script.string and "loadMoreSectors" in script.string:
                sector_found = True
            if script.string and "loadMoreCountries" in script.string:
                countries_found = True
            if sector_found and countries_found:
                break

        # Estrazione dei dati generali
        general_data = get_general_data(soup)

        # Recupera i dati iniziali dei Paesi
        countries_id = find_next_table_id(soup, " Countries ")
        countries_data = extract_data(soup, countries_id) if countries_id else {}

        print("\nGeographic Exposure (Countries):")
        for country, percentage in countries_data.items():
            print(f"  - {country}: {percentage}%")

        # Integra i dati aggiuntivi dei "More Countries" tramite chiamata AJAX
        if countries_found:
            countries_start = time.time()
            while True:
                more_countries_data = load_more_countries(isin, cookies)
                if more_countries_data == {}:
                    continue
                elif more_countries_data != countries_data or time.time() - countries_start > 20:
                    break
            if time.time() - countries_start > 20:
                print("Dati non recuperati correttamente")
            if more_countries_data:
                countries_data.update(more_countries_data)
        else:
            print("Non ci sono countries aggiuntive")

        # Trova gli ID per i Settori
        sectors_id = find_next_table_id(soup, " Sectors ")
        sectors_data = extract_data(soup, sectors_id) if sectors_id else {}

        print("\nSector Exposure:")
        for sector, percentage in sectors_data.items():
            print(f"  - {sector}: {percentage}%")

        # Integra i dati aggiuntivi dei "More Sectors" tramite chiamata AJAX
        if sector_found:
            sector_start = time.time()
            while True:
                more_sectors_data = load_more_sectors(isin, cookies)
                if more_sectors_data == {}:
                    continue
                elif more_sectors_data != sectors_data or time.time() - sector_start > 20:
                    break
            if time.time() - sector_start > 20:
                print("Dati non recuperati correttamente")
            if more_sectors_data:
                sectors_data.update(more_sectors_data)
        else:
            print("Non ci sono sectors aggiuntivi")

        # Recupera il prezzo dell'ETF
        price_data = get_etf_price(isin, cookies)

        # Output ordinato
        print("\nETF Name: ", name)

        # if price_data:
        #     print("\nLatest Price:")
        #     print(f"  - Price: {price_data['price']} EUR")
        #     print(f"  - Date: {price_data['date']}")
        # else:
        #     print("\nLatest Price:")
        #     print("  - Price: Not available")
        #     print("  - Date: Not available")

        # print("\nGeneral Data:")
        # for item in general_data:
        #     print(f"  - {item['name']}: {item['value']}")

        print("\nGeographic Exposure (Countries):")
        for country, percentage in countries_data.items():
            print(f"  - {country}: {percentage}%")

        print("\nSector Exposure:")
        for sector, percentage in sectors_data.items():
            print(f"  - {sector}: {percentage}%")

        return {
            "Name": name,
            "General Data": general_data,
            "Latest Price": {
                "Price": price_data['price'] if price_data else None,
                "Date": price_data['date'] if price_data else None,
            },
            "Geographic Exposure": countries_data,
            "Sector Exposure": sectors_data,
        }

    except Exception as e:
        print(f"Errore durante il recupero dei dati da JustETF: {e}")
        return None

def load_more_countries(isin, cookies):
    try:
        base_url = "https://www.justetf.com/en/etf-profile.html"
        # Genera un timestamp in millisecondi
        current_timestamp = int(time.time() * 1000)

        # Includilo nei parametri della richiesta
        params = {
            "0-1.0-holdingsSection-countries-loadMoreCountries": "",
            "isin": isin,
            "_wicket": "1",
            "_": current_timestamp
        }

        # Trasforma i cookie in un formato compatibile per gli headers
        cookie_header = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

        # Headers della richiesta con i cookie aggiunti
        headers = {
            "authority": "www.justetf.com",
            "method": "GET",
            "scheme": "https",
            "accept": "application/xml, text/xml, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": cookie_header,  # Inserisci i cookie recuperati qui
            "referer": f"https://www.justetf.com/en/etf-profile.html?isin={isin}",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "wicket-ajax": "true",
            "wicket-ajax-baseurl": f"en/etf-profile.html?isin={isin}",
            "x-requested-with": "XMLHttpRequest"
        }

        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code == 200:
            xml_soup = BeautifulSoup(response.text, features="xml")
            # Chiamata al metodo
            second_id = get_second_component_id(xml_soup)
            
            # Trova il componente contenente l'HTML
            component = xml_soup.find("component", {"id": second_id})
            if component:
                # Estrai il contenuto HTML da CDATA
                raw_html = component.string  # Contiene l'HTML puro
                html_soup = BeautifulSoup(raw_html, "html.parser")

                # Trova tutte le righe della tabella
                rows = html_soup.find_all("tr")
                countries_data = {}
                for row in rows:
                    columns = row.find_all("td")
                    if len(columns) == 2:
                        country_name = columns[0].text.strip()
                        percentage = columns[1].find("span").text.strip('%')
                        countries_data[country_name] = float(percentage)

                return countries_data
        else:
            print(f"Errore nella chiamata AJAX per Countries: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Errore durante la chiamata AJAX per More Countries: {e}")
        return {}


# Funzione per caricare i dati aggiuntivi dei Settori tramite chiamata AJAX
def load_more_sectors(isin, cookies):
    try:
        base_url = "https://www.justetf.com/en/etf-profile.html"
        # Genera un timestamp in millisecondi
        current_timestamp = int(time.time() * 1000)

        # Includilo nei parametri della richiesta
        params = {
            "0-1.0-holdingsSection-sectors-loadMoreSectors": "",
            "isin": isin,
            "_wicket": "1",
            "_": current_timestamp
        }
        # Trasforma i cookie in un formato compatibile per gli headers
        cookie_header = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

        # Headers della richiesta con i cookie aggiunti
        headers = {
            "authority": "www.justetf.com",
            "method": "GET",
            "scheme": "https",
            "accept": "application/xml, text/xml, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": cookie_header,  # Inserisci i cookie recuperati qui
            "referer": f"https://www.justetf.com/en/etf-profile.html?isin={isin}",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "wicket-ajax": "true",
            "wicket-ajax-baseurl": f"en/etf-profile.html?isin={isin}",
            # "wicket-focusedelementid": "id170",
            "x-requested-with": "XMLHttpRequest"
        }
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code == 200:
            xml_soup = BeautifulSoup(response.text, features="xml")
            # Chiamata al metodo
            second_id = get_second_component_id(xml_soup)
            
            # Trova il componente contenente l'HTML
            component = xml_soup.find("component", {"id": second_id})
            if component:
                # Estrai il contenuto HTML da CDATA
                raw_html = component.string  # Contiene l'HTML puro
                html_soup = BeautifulSoup(raw_html, "html.parser")

                # Trova tutte le righe della tabella
                rows = html_soup.find_all("tr")
                sectors_data = {}
                for row in rows:
                    columns = row.find_all("td")
                    if len(columns) == 2:
                        sector_name = columns[0].text.strip()
                        percentage = columns[1].find("span").text.strip('%')
                        sectors_data[sector_name] = float(percentage)

            return sectors_data
        else:
            print(f"Errore nella chiamata AJAX per Sectors: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Errore durante la chiamata AJAX per i More Sectors: {e}")
        return {}

# Funzione per trovare l'id della tabella successiva a una specifica intestazione
def find_next_table_id(soup, header_text):
    header = soup.find("h3", text=header_text)
    if header:
        next_table = header.find_next("table")
        if next_table and "id" in next_table.attrs:
            return next_table["id"]
    return None

# Funzione per estrarre i dati generali con eccezioni specifiche
def get_general_data(soup):
    table = soup.find("table", class_="table etf-data-table")
    extracted_data = []
    if table:
        rows = table.find_all("tr")
        for row in rows:
            vallabel = row.find(attrs={"class": "vallabel"})
            val = row.find(attrs={"class": "val"})

            if vallabel and "Fund size" in vallabel.text:
                value = row.find("div").text.strip()
                extracted_data.append({
                    "name": vallabel.text.strip(),
                    "value": value
                })
            elif vallabel and val:
                extracted_data.append({
                    "name": vallabel.text.strip(),
                    "value": val.text.strip()
                })
    return extracted_data

# Funzione per estrarre dati da una tabella (es. Countries, Sectors)
def extract_data(soup, table_id):
    table = soup.find("table", id=table_id)
    data = {}
    if table:
        rows = table.find_all("tr")
        for row in rows:
            columns = row.find_all("td")
            if len(columns) == 2:
                name = columns[0].text.strip()
                percentage = columns[1].find("span").text.strip('%')
                data[name] = float(percentage)
    return data

def get_second_component_id(xml_soup):
    try:
        # Trova tutti gli elementi "component" usando BeautifulSoup
        components = xml_soup.find_all('component')

        # Controlla se ci sono almeno due componenti
        if len(components) > 1:
            # Restituisci il valore dell'attributo id del secondo componente
            return components[1].get('id')
        else:
            return "Non ci sono abbastanza componenti nel file XML."
    except Exception as e:
        return f"Errore durante l'elaborazione: {e}"

def get_etf_price(isin, cookies):
    try:
        # Definizione dell'URL della richiesta API
        url = f"https://www.justetf.com/api/etfs/{isin}/quote"
        # Parametri della richiesta
        params = {
            "locale": "en",
            "currency": "EUR",
            "isin": isin
        }
        # Trasforma i cookie in formato stringa compatibile per gli headers
        cookie_header = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

        # Header della richiesta
        headers = {
            "authority": "www.justetf.com",
            "method": "GET",
            "scheme": "https",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": cookie_header,
            "referer": f"https://www.justetf.com/en/etf-profile.html?isin={isin}",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest"
        }

        # Effettua la richiesta GET
        response = requests.get(url, params=params, headers=headers)

        # Verifica lo stato della risposta
        if response.status_code == 200:
            # Parsing della risposta JSON
            data = response.json()

            # Estrai il prezzo più recente
            latest_price = data["latestQuote"]["raw"]
            quote_date = data["latestQuoteDate"]

            return {"price": latest_price, "date": quote_date}
        else:
            print(f"Errore nella richiesta: {response.status_code}")
            return None
    except Exception as e:
        print(f"Errore durante il recupero del prezzo: {e}")
        return None

# Inseriamo la funzione esistente per calcolare i dati di ciascun ISIN
def get_etf_data_concurrently(isin_list):
    def process_isin(isin_entry):
        isin = isin_entry['isin']
        quotes = isin_entry['quotes']
        data = get_data_from_justetf(isin)
        if data and data["Latest Price"]["Price"]:
            # Calcola il valore totale per questo ETF
            data["Total Value"] = quotes * data["Latest Price"]["Price"]
            data["Quotes"] = quotes
        else:
            data["Total Value"] = 0
            data["Quotes"] = quotes
        return {isin: data}

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_isin, isin): isin for isin in isin_list}
        for future in futures:
            result = future.result()
            results.update(result)
    return results

# Funzione per calcolare esposizioni pesate
def calculate_weighted_exposures(etf_data):
    countries = {}
    sectors = {}
    total_portfolio_value = sum(etf["Total Value"] for etf in etf_data.values())

    for data in etf_data.values():
        if data["Total Value"] > 0:
            weight = data["Total Value"] / total_portfolio_value
            # Pesi per Countries
            for country, percentage in data["Geographic Exposure"].items():
                countries[country] = countries.get(country, 0) + percentage * weight
            # Pesi per Sectors
            for sector, percentage in data["Sector Exposure"].items():
                sectors[sector] = sectors.get(sector, 0) + percentage * weight

    return countries, sectors, total_portfolio_value

def create_pie_chart(data, title, threshold=3):
    # Raggruppa categorie minori se necessario
    other_value = 0
    filtered_data = {}
    for key, value in data.items():
        if value < threshold:
            other_value += value
        else:
            filtered_data[key] = value

    if other_value > 0:
        filtered_data["Other"] = other_value

    # Crea il grafico
    labels = list(filtered_data.keys())
    sizes = list(filtered_data.values())
    explode = [0.1 if size < threshold else 0 for size in sizes]  # Evidenzia "Other" o categorie piccole

    fig, ax = plt.subplots()
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct=lambda pct: f'{pct:.1f}%' if pct > 1 else '', 
        startangle=90, textprops={'fontsize': 9}, pctdistance=0.85, explode=explode
    )

    # Aggiungi annotazioni esterne per mantenere i nomi visibili
    for i, text in enumerate(texts):
        if sizes[i] < threshold:
            text.set_color('grey')  # Colora i testi piccoli in grigio
        text.set_fontsize(10)

    for autotext in autotexts:
        autotext.set_fontsize(8)
        autotext.set_color('black')  # Valori percentuali

    # Disegna un cerchio centrale per creare l'effetto di "doughnut"
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)

    # Titolo del grafico
    plt.title(title, fontsize=14)

    return fig



# Main con Streamlit
def main():
    # st.title("ETF Portfolio Overview")

    # # Recupera i dati degli ETF
    # st.header("Portfolio Data")
    # st.write("Sto recuperando i dati per gli ETF, attendere...")

    isin_list = [#{'isin' : "LU2195226068", 'quotes' : 10},  # Amundi net zero euro
            #  {'isin' : "IE00BHZPJ239", 'quotes' : 10},  # MSCI EM
             {'isin' : "IE00BFNM3D14", 'quotes' : 10},  # MSCI EURO
            #  {'isin' : "LU1437017350", 'quotes' : 10},  # AMUNDI EM
            #  {'isin' : "IE00BHZPJ569", 'quotes' : 10},  # MSCI World
            #  {'isin' : "IE00B3VWN393", 'quotes' : 10},  # Treasury 3-7yr
            #  {'isin' : "IE00BH04GL39", 'quotes' : 10}, # Euro gov bonds
            #   {'isin' : "IE00B5BMR087", 'quotes' : 10}, # S&P 500
    ]
    etf_data = get_etf_data_concurrently(isin_list)

#    # Stampa i dati di countries e sectors per ogni ISIN
#     for isin, data in etf_data.items():
#         print(f"\nISIN: {isin}")
#         print("Countries Exposure:")
#         for country, percentage in data["Geographic Exposure"].items():
#             print(f"  - {country}: {percentage}%")
#         print("Sector Exposure:")
#         for sector, percentage in data["Sector Exposure"].items():
#             print(f"  - {sector}: {percentage}%")
#     # Visualizza i dati degli ETF
#     portfolio_value = 0
#     # for isin, data in etf_data.items():
#     #     st.subheader(f"ETF: {data['Name']}")
#     #     st.write(f"Latest Price: {data['Latest Price']['Price']} EUR")
#     #     st.write(f"Total Value: {data['Total Value']} EUR")
#     #     st.write(f"Quotes: {data['Quotes']}")

#     # Calcolo esposizioni
#     countries, sectors, portfolio_value = calculate_weighted_exposures(etf_data)

#     st.header("Portfolio Overview")
#     st.write(f"Total Portfolio Value: {portfolio_value} EUR")

#     # Crea due colonne per i grafici
#     col1, col2 = st.columns(2)

#     # Grafico per l'esposizione geografica
#     with col1:
#         st.subheader("Geographic Exposure")
#         country_chart = create_pie_chart(countries, "Geographic Exposure by Countries")
#         st.pyplot(country_chart)

#     # Grafico per l'esposizione settoriale
#     with col2:
#         st.subheader("Sector Exposure")
#         sector_chart = create_pie_chart(sectors, "Sector Exposure by Sectors")
#         st.pyplot(sector_chart)

# Esegui l'app Streamlit
if __name__ == "__main__":
    main()

# Esempio di utilizzo
# isin_list = [{'isin' : "LU2195226068", 'quotes' : 18},  # Amundi net zero euro
#              {'isin' : "IE00BHZPJ239", 'quotes' : 33},  # MSCI EM
#              {'isin' : "IE00BFNM3D14", 'quotes' : 70},  # MSCI EURO
#              {'isin' : "LU1437017350", 'quotes' : 1},  # AMUNDI EM
#              {'isin' : "IE00BHZPJ569", 'quotes' : 163},  # MSCI World
#              {'isin' : "IE00B3VWN393", 'quotes' : 16},  # Treasury 3-7yr
#              {'isin' : "IE00BH04GL39", 'quotes' : 210}] # Euro gov bonds
# # isin = "IE00B4L5Y983"  # Inserisci il codice ISIN dell'ETF
# isin = "IE00BH04GL39"
# data = get_data_from_justetf(isin)
