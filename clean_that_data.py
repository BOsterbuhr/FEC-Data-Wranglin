from src.data.clean_data import clean_data
import os
import fnmatch


path_pattern = "*.csv"
files = os.listdir("data/raw_data/")
for csv in files:
    if fnmatch.fnmatch(csv, path_pattern):
        clean_data(csv, .8, 3)

