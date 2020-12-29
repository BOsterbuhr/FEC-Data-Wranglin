import os
import pandas as pd
import fnmatch
from src.data.data_fetcher import DataFetcher
from src.data.NYC_vars import all_zips, committee_types, target_years

for year in target_years:
    for type in committee_types:
        for zip in all_zips:
            fetcher = DataFetcher(two_year_transaction_period=year, recipient_committee_type=type, contributor_zip=zip)
            fetcher.api_starting_url_container
            fetcher.gimmie_data()
            fetcher.save_df_data()

# combine all csv into one master csv
files = os.listdir("data/raw_data")
combined_csv = pd.concat( [ pd.read_csv(f'/Users/brodyosterbuhr/Desktop/FEC_NYC_DATA/data/raw_data/{file}', index_col=0) for file in files if fnmatch.fnmatch(file, pattern := '*.csv') ] )
combined_csv.to_csv( "data/raw_data/combined_csv.csv", index=False )
for file in files:
    if file != "combined_csv.csv":
        os.remove(file) 