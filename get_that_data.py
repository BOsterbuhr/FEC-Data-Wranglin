from src.data.data_fetcher import DataFetcher



fetcher = DataFetcher("2020", "S")
fetcher.api_starting_url_container
fetcher.gimmie_data(record_limit=5)
fetcher._build_df()
fetcher._save_df_data()