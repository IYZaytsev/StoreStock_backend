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
            # hitting  the UPC database
            barcode_api = f'https://api.upcdatabase.org/product/{product_id}?apikey={barcode_api_key}'
            result = python_curl(barcode_api)
            object_from_result = ujson.loads(result)

            # if the barcode is not in the UPC database, json response will have field error
            if "error" in object_from_result:
                obj = {
                    'result': "no data can be found about this product",
                }
                response = jsonify(obj)
                response.status_code = 200
                return response

            # hitting the wikipedia search endpoint
            percent_encoded_name = quote(object_from_result['brand'], safe='')
            wikipedia_search_api = f"https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch={percent_encoded_name}20Brand&srnamespace=0&srlimit=15"
            result = python_curl(wikipedia_search_api)
            object_from_result = ujson.loads(result)
            # hitting wikipedia convert page id to url endpoint

            # if length of search array, no data on wikipedia can be found return 
            if len(object_from_result["query"]["search"]) == 0:
                obj = {
                    'result': "no data can be found about this product",
                }
                response = jsonify(obj)
                response.status_code = 200
                return response
            page_id = object_from_result["query"]["search"][0]["pageid"]
            wikipedia_resolve_id_to_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=info&pageids={page_id}&format=json&inprop=url"
            result = python_curl(wikipedia_resolve_id_to_url)
            object_from_result = ujson.loads(result)
            obj = {
                'result': object_from_result,
            }
            barcodes[product_id] = object_from_result
            response = jsonify(obj)
            response.status_code = 200
            return response

    return app                            


# A general purpose curl that returns json as a string
def python_curl(url):
    # pyCurl set up, buffer is used to hold HTML
    # and creating a pycurl object called "c"
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    #Follow redirect set to true
    c.setopt(c.FOLLOWLOCATION, True)
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