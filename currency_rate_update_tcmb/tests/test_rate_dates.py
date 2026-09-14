from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestRateDates(TransactionCase):
    def test_historical_range_keeps_exclusive_end(self):
        provider = self.env["res.currency.rate.provider"].create({"service": "TCMB"})
        rates = {"USD": {"ForexBuying": 0.025}}
        with patch.object(type(provider), "get_tcmb_currency_data", return_value=rates):
            result = provider._obtain_rates(
                "TRY", ["USD"], date(2020, 1, 1), date(2020, 1, 3)
            )
        self.assertEqual(result, {"2020-01-01": rates, "2020-01-02": rates})
