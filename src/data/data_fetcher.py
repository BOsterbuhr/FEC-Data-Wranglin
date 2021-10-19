import os
import json
import time
import requests
import fnmatch
import pandas as pd


class APIStartingURLContainer:
    """
    Dummy container used to enforce that _get_total_pages_for_call() is only
    accessed through DataFetcher
    """

    def __init__(self, url: str):
        self.url = url

    def __str__(self):
        return self.url


def _get_total_pages_for_call(api_starting_url_container: APIStartingURLContainer):
    """
    At the bottom of the JSON, on the first page of an API call, there's a 'pagination' key
    that has a 'pages' key. This number represents the total number of result pages for this
    API call.

    Function performs a GET request on `api_starting_url_container` and returns integer with the total number
    of pages available to pull.

    Parameters:
        api_starting_url_container: APIStartingURLContainer
            Generated from `_make_api_url()`

    Returns:
        pages: int
            Number of pages remaining of `api_starting_url_container`
    """
    if not isinstance(api_starting_url_container, APIStartingURLContainer):
        raise TypeError(
            "_get_total_pages_for_call should only be called with an"
            + " `api_starting_url_container` object, built from `make_api_url()`"
        )

    uh = requests.get(api_starting_url_container.url)
    data = uh.text
    info = json.loads(data)

    pages = info["pagination"]["pages"]
    return pages


def _make_api_url(
    two_year_transaction_period: int, recipient_committee_type: str, contributor_zip: str = None, contributor_state: str = None, contributor_city: str = None
) -> str:
    """
    Build the `starting_url` to get campaign donation receipt data of individual's donations for a two year time period.

    Parameters:
        two_year_transaction_period: int
            A two-year period that is derived from the year a transaction took place,
            if you want an odd-number year enter the following even-numbered year.
                i.e. want 2019, enter 2020.

        recipient_committee_type: str
            The one-letter type code of the office the political campaign was for
                (H = House) (S = Senate) (P = Presidential).

    Returns:
        A URL string for either House, Senate, or Presidential political campaigns from a specified two year period.
    """

    base_api_url = "https://api.open.fec.gov/v1/schedules/schedule_a/?"
    set_parameters = "&sort=-contribution_receipt_date&sort_hide_null=true&sort_null_only=false&is_individual=true&contributor_type=individual&per_page=100"

    api_key = os.environ.get("FEC_API_KEY")

    if not api_key:
        print(
            "No value found for environment variable: FEC_API_KEY. Using DEMO_KEY instead."
        )
        api_key = "DEMO_KEY"

    two_year_transaction_period = _handle_two_year_transaction_period(
        two_year_transaction_period
    )

    recipient_committee_type = _handle_recipient_committee_type(
        recipient_committee_type
    )

    location_query = _handle_location_query(
        contributor_zip, contributor_state, contributor_city)

    starting_url = (f"{base_api_url}{two_year_transaction_period}&api_key={api_key}{recipient_committee_type}{location_query}{set_parameters}"
                    )
    return APIStartingURLContainer(url=starting_url)


def _handle_two_year_transaction_period(two_year_transaction_period: str):
    if str(two_year_transaction_period).isnumeric():
        two_year_transaction_period = int(two_year_transaction_period)
        if two_year_transaction_period % 2 != 0:
            two_year_transaction_period = two_year_transaction_period + 1
        if two_year_transaction_period in range(2004, 2021):
            return f"two_year_transaction_period={str(two_year_transaction_period)}"
    print("Invalid input, defaulting to 2020.")
    return "two_year_transaction_period=2020"


def _handle_recipient_committee_type(recipient_committee_type: str) -> str:
    possible_types = ["H", "HOUSE", "S", "SENATE", "P", "PRESIDENTIAL"]
    recipient_committee_type = recipient_committee_type.upper()
    if recipient_committee_type in possible_types:
        return f"&recipient_committee_type={recipient_committee_type[:1]}"
    elif recipient_committee_type in ["A", "ALL"]:
        return "&recipient_committee_type=H&recipient_committee_type=P&recipient_committee_type=S&recipient_committee_type=V&recipient_committee_type=W"
    else:
        print("Invalid input, defaulting to Presidential")
        return "&recipient_committee_type=P"


def _handle_location_query(contributor_zip: str, contributor_state: str, contributor_city: str) -> str:
    location_query = ""
    if contributor_zip:
        if contributor_zip.isnumeric():
            contributor_zip = contributor_zip[:5]
            location_query += f"&contributor_zip={contributor_zip}"
    if contributor_state:
        location_query += f"&contributor_state={contributor_state}"
    if contributor_city:
        contributor_city = contributor_city.upper()
        location_query += f"&contributor_city={contributor_city}"

    return location_query


class DataFetcher:
    """
    Instantiated with the year and President/Senate/House level you're interested in
    and provides a `gimmie_data()` method that uses this info to pull all of the
    relevant FEC information into a `pandas.DataFrame`

    Parameters:
        two_year_transaction_period: int
            A two-year period that is derived from the year a transaction took place,
            if you want an odd-number year enter the following even-numbered year.
                i.e. want 2019, enter 2020.

        recipient_committee_type: str
            The one-letter type code of the office the political campaign was for
                (H = House) (S = Senate) (P = Presidential).

    Returns:
        complete_list is returned after getting all transactions from a page.

    """

    def __init__(self, two_year_transaction_period: int, recipient_committee_type: str, contributor_zip: str = None, contributor_state: str = None, contributor_city: str = None):
        self.api_starting_url_container = _make_api_url(
            two_year_transaction_period, recipient_committee_type, contributor_zip, contributor_state, contributor_city
        )

        self.two_year_transaction_period = two_year_transaction_period
        self.recipient_committee_type = recipient_committee_type
        self.contributor_zip = contributor_zip
        self.contributor_state = contributor_state
        self.contributor_city = contributor_city

        self.total_pages = _get_total_pages_for_call(
            self.api_starting_url_container)

        self.starting_url = self.api_starting_url_container.url

        self.complete_list = []
        self.df = None

        self.pages_pulled = 0
        self.api_calls_per_min = 1  # first info page is a call

    @property
    def under_rate_limit(self):
        """
        Is our current per-hour API calls below the rate limit
        """
        return self.api_calls_per_min < 120

    @property
    def rate_limit_cycles_to_complete(self):
        """
        If we can pull 1000 pages in an hour, then we'll do as many
        1000-pull hours as we need to, plus one more to get the extra
        n < 1000 pages
        """
        total_cycles = (self.total_pages // 1000) + 1
        return total_cycles

    async def gimmie_data(self, sleep_timer: int = 0, record_limit: int = None):
        """
        Uses the URL generated by the class constructor to pull and parse
        multiple pages, while keeping below the API call-per-hour threshold.

        Parameters:
            sleep_timer: int (default=3600)
                Time, in seconds, we wait when we hit the 1000 call limit

            record_limit: int (optional)
                Number of records to pull before exiting the run
        Result:
            You automagically have a DataFrame from the results of self.current_list
        """
        while self.pages_pulled < self.total_pages:
            if record_limit:
                if self.pages_pulled > record_limit:
                    break
            try:
                if self.under_rate_limit:
                    self.api_calls_per_min += 1

                    self._get_next_page()
                    self._get_transactions_on_page()
                    
                    self.pages_pulled += 1

                else:
                    print(self.pages_pulled)
                    #print("waiting 1 min")
                    time.sleep(sleep_timer)
                    self.api_calls_per_min = 1
            except:
                continue
        self._build_df()

    def _get_next_page(self):
        """
        Adds two items to api_starting_url to get to the next page of transactions.

        Description:
            Takes the api_starting_url and concatenates last_index and last_contribution_receipt_date
            to get the next page of transactions.
        """

        if self.pages_pulled >= 1:
            url = f"{self.starting_url}&last_index={self.last_index}&last_contribution_receipt_date={self.last_contribution_receipt_date}"
        else:
            url = self.starting_url

        uh = requests.get(url)
        data = uh.text
        self.info = json.loads(data)
        self.last_index = self.info["pagination"]["last_indexes"]["last_index"]
        self.last_contribution_receipt_date = self.info["pagination"][
            "last_indexes"]["last_contribution_receipt_date"]

    def _get_transactions_on_page(self):
        """
        Loops over the transactions on a page using self.info from get_next_page.
        Puts that data into current_list.
        Puts current_list into complete_list.
        Gets last_index and last_contribution_receipt_date to pass to get_next_page.
        Returns complete_list with transactions from page.
        """

        # Pull out the data we want from each transaction on a page and add it to the complete_list
        for item in self.info["results"]:

            # Handle non-numeric zip codes
            contributor_zip = item["contributor_zip"]
            try:
                if contributor_zip.isnumeric():
                    if len(contributor_zip) < 5:
                        contributor_zip = 99999
                    elif len(contributor_zip) > 5:
                        contributor_zip = int(contributor_zip[0:5])
                    contributor_zip = int(contributor_zip)
                else:
                    contributor_zip = 99999
            except:
                contributor_zip = 99999
            
            # Handle null party values
            party = item["committee"]["party"]    
            if item["committee"]["name"] == "ACTBLUE":
                party = "DEM"
            elif item["committee"]["name"] == "WINRED":
                party = "REP"
            elif item["committee"]["party"] == None:
                party = "OTH"
            else:
                party = item["committee"]["party"]
            
            # Bundle the data into a list and add it to the complete_list
            self.complete_list.append(
                current_list := [
                    committe_name := item["committee"]["name"],
                    contribution_receipt_amount := item["contribution_receipt_amount"],
                    contributor_occupation := item["contributor_occupation"],
                    contributor_employer := item["contributor_employer"],
                    contributor_street_1 := item["contributor_street_1"],
                    contributor_street_2 := item["contributor_street_2"],
                    contributor_city := item["contributor_city"],
                    contributor_state := item["contributor_state"],
                    contributor_zip,
                    party,
                ]
            )

    def _build_df(self):
        self.df = pd.DataFrame(
            self.complete_list,
            columns=[
                "committee_name",
                "contribution_receipt_amount",
                "contributor_occupation",
                "contributor_employer",
                "contributor_street_1",
                "contributor_street_2",
                "contributor_city",
                "contributor_state",
                "contributor_zip",
                "party",
            ],
        )
        self.df.fillna(value="", inplace=True)


    async def summarize_df(self):
        """
        Summarizes the DataFrame by party and returns a DataFrame with the results.
        """
        df = self.df
        print(df.info)
        print(df.head())
        print(df.describe())
        return df


    async def save_df_data(self):
        files = os.listdir("data/raw_data")
        for name in files:
            if fnmatch.fnmatch(name, pattern := f"*_{self.recipient_committee_type}_in_{self.two_year_transaction_period}_for_{self.contributor_city}_{self.contributor_state}_{self.contributor_zip}.csv"):
                os.remove("data/raw_data/" + name)
                self.df.to_csv(
                    f'data/raw_data/{self.pages_pulled}_of_{self.total_pages}_for_{self.recipient_committee_type}_in_{self.two_year_transaction_period}_for_{self.contributor_city}_{self.contributor_state}_{self.contributor_zip}.csv')
        self.df.to_csv(
            f'data/raw_data/{self.pages_pulled}_of_{self.total_pages}_for_{self.recipient_committee_type}_in_{self.two_year_transaction_period}_for_{self.contributor_city}_{self.contributor_state}_{self.contributor_zip}.csv')
