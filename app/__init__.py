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
def create_app(config_name):

    # Creating a app
    app = FlaskAPI(__name__, instance_relative_config=True)
    app.config.from_object(app_config[config_name])
    app.config.from_pyfile('config.py')

    # using a dictionary to cache api results to save on requests
    barcodes = {}
    @app.route('/product/<string:product_id>', methods=['GET'])
    def return_product_info(product_id, **kwargs):
        # first check the cache to see if this item has been queried before the UPC database
        if len(barcodes.keys()) >= 1 and product_id in barcodes.keys():
            print("Object found in cache")
            obj = {
                'result': barcodes[product_id],
            }
            response = jsonify(obj)
            response.status_code = 200
            return response
        else:
            barcode_api_key = os.getenv("UPC_API_KEY")
            header = ['x-rapidapi-host: product-data1.p.rapidapi.com', f'x-rapidapi-key:{barcode_api_key}']
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
            object_from_result = wikipedia_search_with_brand(product_object['items']['brand'])

            # hitting wikipedia convert page id to url endpoint
            # parent company is P355 on wikipedia property
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
            parent_corp = get_parent_corp(object_from_result['query']['pages'][f"{page_id}"]['title'])

            if parent_corp != object_from_result['query']['pages'][f"{page_id}"]['title']:
                object_from_result = wikipedia_search_with_brand(parent_corp)
                page_id = object_from_result["query"]["search"][0]["pageid"]
                object_from_result = get_url_from_page_id(page_id)

            obj = {
                'parent_company': object_from_result['query']['pages'][f"{page_id}"],
                'product':product_object['items'],
            }
            barcodes[product_id] = obj
            response = jsonify(obj)
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
    wikipedia_search_api = f"https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch={percent_encoded_name}20Brand&srnamespace=0&srlimit=15"

    result = python_curl(wikipedia_search_api)
    return ujson.loads(result)

# hits wikidata api to get parent corporation until no parent company is found
def get_parent_corp(title):
    # looking for property P749 in json
    parent_company_so_far = title
    percent_encoded_title = quote(title, safe='')
    get_info_box = f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&props=claims&titles={percent_encoded_title}'

    result = python_curl(get_info_box)
    object_from_result = ujson.loads(result)
    entity_id = list(object_from_result['entities'].keys())[0]
    if "P749" in object_from_result['entities'][entity_id]['claims']:
        parent_company_entity_id = object_from_result['entities'][entity_id]['claims']["P749"][0]['mainsnak']['datavalue']['value']['id']
    else:
        return parent_company_so_far
    get_parent_title = f'https://www.wikidata.org/wiki/Special:EntityData/{parent_company_entity_id}.json'

    result = python_curl(get_parent_title)
    object_from_result = ujson.loads(result)
    parent_company_so_far = object_from_result['entities'][parent_company_entity_id]["labels"]['en']['value']
    return parent_company_so_far

# A general purpose curl that returns json as a string
def python_curl(url, header=None):
    # pyCurl set up, buffer is used to hold HTML
    # and creating a pycurl object called "c"
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    #Follow redirect set to true
    c.setopt(c.FOLLOWLOCATION, True)
    #setting optional header
    if header != None:
      c.setopt(pycurl.HTTPHEADER, header)  

    #Uncomment line below if problem with pycurl occurs
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