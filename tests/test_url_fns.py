import pytest
from unittest.mock import Mock

from src.data.data_fetcher import (
    _get_total_pages_for_call,
    _handle_two_year_transaction_period,
    _handle_recipient_committee_type,
    APIStartingURLContainer,
)


@pytest.fixture
def mock_get_response():
    """
    Instead of actually going out and calling the site,
    this function intercepts `requests.get()` calls and
    has it read from the staged file, instead
    """
    with open("./tests/2020_house.json") as f:
        return f.read()


class TestTotalPagesForCall:
    def test_bad_data_type(self):
        with pytest.raises(TypeError):
            _get_total_pages_for_call("www.google.com")

    def test_get_page_from_json(self, monkeypatch, mock_get_response):
        """
        Patched over the site connection code to read from local JSON.
        This function checks that we find the correct value for
        ['pagination']['pages']
        """
        mock_get = Mock(return_value=Mock(text=mock_get_response))
        mock_requests = Mock(get=mock_get)
        monkeypatch.setattr("src.data.data_fetcher.requests", mock_requests)

        expected = 40743
        result = _get_total_pages_for_call(APIStartingURLContainer("www.google.com"))

        assert result == expected


class TestTransactionPeriod:
    def test_allows_odd(self):
        expected = "2014"

        result = _handle_two_year_transaction_period("2013")
        assert expected == result

    def test_character_error(self, capsys):
        error_msg = "Invalid input, defaulting to 2020.\n"
        expected = "2020"

        result = _handle_two_year_transaction_period("BoB")
        captured = capsys.readouterr().out
        assert expected == result
        assert captured == error_msg

    def test_year_out_of_range(self, capsys):
        error_msg = "Invalid input, defaulting to 2020.\n"
        expected = "2020"

        result = _handle_two_year_transaction_period("2021")
        captured = capsys.readouterr().out
        assert expected == result
        assert captured == error_msg

        expected = "2004"
        result = _handle_two_year_transaction_period("2003")
        captured = capsys.readouterr().out
        assert expected == result
        assert captured == ""

    def test_allows_int(self, capsys):
        expected = "2012"

        result = _handle_two_year_transaction_period(2012)
        assert expected == result


class TestCommitteeType:
    def test_allows_lower(self):
        expected = "H"

        result = _handle_recipient_committee_type("h")
        assert expected == result

        result = _handle_recipient_committee_type("house")
        assert expected == result

    def test_allows_lower_s(self):
        expected = "S"
        result = _handle_recipient_committee_type("s")
        assert expected == result

        result = _handle_recipient_committee_type("senate")
        assert expected == result

    def test_allows_lower_p(self, capsys):
        """
        This one additionally tests that the error message doesn't fire
        """
        error_msg = "Invalid input, defaulting to Presidential\n"
        expected = "P"

        result = _handle_recipient_committee_type("p")
        captured = capsys.readouterr().out
        assert expected == result
        assert captured == ""

        result = _handle_recipient_committee_type("presidential")
        captured = capsys.readouterr().out
        assert expected == result
        assert captured == ""
