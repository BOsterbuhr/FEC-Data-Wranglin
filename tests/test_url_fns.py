from src.data.data_fetcher import (
    _handle_two_year_transaction_period,
    _handle_recipient_committee_type,
)


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
