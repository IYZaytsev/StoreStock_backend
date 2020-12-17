import csv

path =  './csv/parent-companies.csv'

with open(path, 'r', encoding='utf-8', errors='ignore') as infile, open(path + 'final.csv', 'w') as outfile:
     inputs = csv.reader(infile)
     output = csv.writer(outfile)

     for index, row in enumerate(inputs):
         output.writerow(row)