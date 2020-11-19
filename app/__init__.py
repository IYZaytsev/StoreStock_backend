from flask_api import FlaskAPI

from flask import request, jsonify, abort
# local import
from instance.config import app_config
# app_config is a dictionary that turns a string into
# a function that sets some variables
import os
import ujson
import json
import re
import pycurl
from io import BytesIO
from urllib.parse import quote
import yfinance as yf
from datetime import datetime
import ftfy  

def create_app(config_name):

    # Creating a app
    app = FlaskAPI(__name__, instance_relative_config=True)
    app.config.from_object(app_config[config_name])
    app.config.from_pyfile('config.py')

    # using a dictionary to cache api results to save on requests
    barcodes = {}
    stock_prices = {}

    @app.route('/product/<string:product_id>', methods=['GET'])
    def return_product_info(product_id, **kwargs):
        # first check the cache to see if this item has been queried before the UPC database
        if len(barcodes.keys()) >= 1 and product_id in barcodes.keys():
            obj = {
                'result': barcodes[product_id],
            }
            response = jsonify(obj)
            response.status_code = 200
            return response
        else:
            barcode_api_key = os.getenv("UPC_API_KEY")
            header = ['x-rapidapi-host: product-data1.p.rapidapi.com',
                      f'x-rapidapi-key:{barcode_api_key}']
            # hitting  the UPC database
            barcode_api = f'https://product-data1.p.rapidapi.com/lookup?upc={product_id}'
            result = python_curl(barcode_api, header)
            product_object = ujson.loads(result)

            # if the barcode is not in the UPC database, json response will have False in success
            if not product_object['success']:
                obj = {
                    'result': "no data can be found about this product",
                }
                response = jsonify(obj)
                response.status_code = 200
                return response

            # hitting the wikipedia search endpoint
            object_from_result = wikipedia_search_with_brand(
                product_object['items']['brand'])

            # hitting wikipedia convert page id to url endpoint
            # if length of search array, no data on wikipedia can be found return
            if len(object_from_result["query"]["search"]) == 0:
                obj = {
                    'result': "no data can be found about this product",
                }
                response = jsonify(obj)
                response.status_code = 200
                return response

            # hitting the wikipedia url from page id end point
            page_id = object_from_result["query"]["search"][0]["pageid"]
            object_from_result = get_url_from_page_id(page_id)
            # doing everything above but for parent company,
            # if no parent company is found, just return existing object
            parent_corp = get_parent_corp(
                object_from_result['query']['pages'][f"{page_id}"]['title'], 1)
            ticker_symbol = "none"
            if parent_corp['company_name'] != object_from_result['query']['pages'][f"{page_id}"]['title']:
                object_from_result = wikipedia_search_with_brand(
                    parent_corp['company_name'])
                page_id = object_from_result["query"]["search"][0]["pageid"]
                object_from_result = get_url_from_page_id(page_id)
                ticker_symbol = get_parent_corp_stock_ticker(parent_corp['id'])

            # if no parent company is found, just return existing object
            parent_corp = get_parent_corp(
                object_from_result['query']['pages'][f"{page_id}"]['title'], 2)
            if parent_corp['company_name'] != object_from_result['query']['pages'][f"{page_id}"]['title']:
                object_from_result = wikipedia_search_with_brand(
                    parent_corp['company_name'])
                page_id = object_from_result["query"]["search"][0]["pageid"]
                object_from_result = get_url_from_page_id(page_id)
                ticker_symbol = get_parent_corp_stock_ticker(parent_corp['id'])

            obj = {
                'parent_company': object_from_result['query']['pages'][f"{page_id}"],
                'ticker': ticker_symbol,
                'product': product_object['items'],
            }
            barcodes[product_id] = obj
            response = jsonify(obj)
            response.status_code = 200
            return response

    @app.route('/company/<string:ticker>', methods=['GET'])
    def return_company_stock_info(ticker, **kwargs):
        # valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        # Regular trading on the New York Stock Exchange and the Nasdaq electronic market ends at 4 p.m. EST.
        now = datetime.now()
        today = now.date().strftime("%m/%d/%Y")
        if (ticker == "NSN"):
            ticker = "NSRGY"
        ticker_and_date = today + ticker
        if ticker_and_date in stock_prices:
            response = jsonify(stock_prices[ticker_and_date])
            response.status_code = 200
            return response

        stock = yf.Ticker(ticker)
        stock_info = stock.info
        summary = ftfy.fix_text(stock_info["longBusinessSummary"])
        open_close = stock.history(period="5d")
        list_of_prices = []
        for x in range(5):
            obj = {
                "open": open_close["Open"][x],
                "close": open_close["Close"][x]
            }
            list_of_prices.append(obj)
        if "state" not in stock_info:
            state = "none"
        else:
            state = stock_info["state"]
        return_obj = {
            "name": stock_info['longName'],
            "summary": summary,
            "logo_url": stock_info['logo_url'],
            "5day_prices": list_of_prices,
            "fiftyTwoWeekHigh": stock_info['fiftyTwoWeekHigh'],
            "fiftyTwoWeekLow": stock_info['fiftyTwoWeekLow'],
            "marketCap": stock_info['marketCap'],
            "city":stock_info['city'],
            "state":state,
            "country":stock_info["country"]

        }
        response = jsonify(return_obj)
        stock_prices[ticker_and_date] = return_obj
        response.status_code = 200
        return response
    return app


def get_url_from_page_id(page_id):
    wikipedia_resolve_id_to_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=info&pageids={page_id}&format=json&inprop=url"
    result = python_curl(wikipedia_resolve_id_to_url)
    return ujson.loads(result)

# returns the search results for title brand


def wikipedia_search_with_brand(title):

    # hitting the wikipedia search endpoint
    percent_encoded_name = quote(title, safe='')
    wikipedia_search_api = f"https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch={percent_encoded_name}&srnamespace=0&srlimit=15"

    result = python_curl(wikipedia_search_api)
    return ujson.loads(result)

# hits wikidata api to get parent corporation until no parent company is found


def get_parent_corp(title, round):
    # looking for property P749 in json or P127
    parent_company_so_far = title
    percent_encoded_title = quote(title, safe='')
    get_info_box = f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&props=claims&titles={percent_encoded_title}'

    result = python_curl(get_info_box)
    object_from_result = ujson.loads(result)
    parent_company_entity_id = 0
    entity_id = list(object_from_result['entities'].keys())[0]
    if "P749" in object_from_result['entities'][entity_id]['claims']:
        parent_company_entity_id = object_from_result['entities'][entity_id][
            'claims']["P749"][0]['mainsnak']['datavalue']['value']['id']
    elif "P127" in object_from_result['entities'][entity_id]['claims'] and round == 1:
        parent_company_entity_id = object_from_result['entities'][entity_id][
            'claims']["P127"][0]['mainsnak']['datavalue']['value']['id']
    elif "P176" in object_from_result['entities'][entity_id]['claims'] and round == 1:
        parent_company_entity_id = object_from_result['entities'][entity_id][
            'claims']["P176"][0]['mainsnak']['datavalue']['value']['id']
    else:
        return {'company_name': parent_company_so_far, 'id': 0}

    get_parent_title = f'https://www.wikidata.org/wiki/Special:EntityData/{parent_company_entity_id}.json'

    result = python_curl(get_parent_title)
    object_from_result = ujson.loads(result)
    parent_company_so_far = object_from_result['entities'][parent_company_entity_id]["labels"]['en']['value']
    return {'company_name': parent_company_so_far, 'id': parent_company_entity_id}


def get_parent_corp_stock_ticker(id):
    # looking for property P249 in json
    get_info_box = f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&props=claims&ids={id}'
    result = python_curl(get_info_box)
    object_from_result = ujson.loads(result)
    if "P414" in object_from_result['entities'][id]['claims'] and "qualifiers" in object_from_result['entities'][id]['claims']["P414"][0]:
        return object_from_result['entities'][id]['claims']["P414"][0]['qualifiers']['P249'][0]['datavalue']['value']
    return "none"

# A general purpose curl that returns json as a string


def python_curl(url, header=None):
    # pyCurl set up, buffer is used to hold HTML
    # and creating a pycurl object called "c"
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    # Follow redirect set to true
    c.setopt(c.FOLLOWLOCATION, True)
    # setting optional header
    if header != None:
        c.setopt(pycurl.HTTPHEADER, header)

    # Uncomment line below if problem with pycurl occurs
    #c.setopt(c.VERBOSE, True)
    c.setopt(c.WRITEDATA, buffer)
    # User agent to make websites think you are a browser
    c.setopt(
        c.USERAGENT,
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:42.0) Gecko/20100101 Firefox/42.0"
    )
    try:
        c.perform()
    except pycurl.error as e:
        print(e)

    c.close()
    body = buffer.getvalue()
    string_body = body.decode('iso-8859-1')
    return string_body
