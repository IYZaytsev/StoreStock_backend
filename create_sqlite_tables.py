import sqlite3
import pandas as pd

db = sqlite3.connect("store_stock.db")
parent_companies = pd.read_csv("./csv/parent-companies-csvfinal.csv")
nyse_listed = pd.read_csv("./csv/nyse-listed_csv.csv")
amex_listed = pd.read_csv("./csv/amex.csv")
nasdaq_listed = pd.read_csv("./csv/nasdaq.csv")
parent_companies.to_sql('parent_companies', db, if_exists='append', index=False)
nyse_listed.to_sql('nyse_listed', db, if_exists='append', index=False)
amex_listed.to_sql('amex_listed', db, if_exists='append', index=False)
nasdaq_listed.to_sql('nasdaq_listed', db, if_exists='append', index=False)