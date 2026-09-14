# Copyright 2023 Tecnativa - Ernesto Tejeda
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


from datetime import timedelta
from unittest.mock import patch

from requests import Response

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import common


class TestResCurrencyRateProviderXE(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Company = cls.env["res.company"]
        cls.CurrencyRate = cls.env["res.currency.rate"]
        cls.CurrencyRateProvider = cls.env["res.currency.rate.provider"]

        cls.today = fields.Date.today()
        cls.eur_currency = cls.env.ref("base.EUR")
        cls.usd_currency = cls.env.ref("base.USD")
        cls.company = cls.Company.create(
            {"name": "Test company", "currency_id": cls.eur_currency.id}
        )
        cls.env.user.company_ids += cls.company
        cls.env.company = cls.company
        cls.xe_provider = cls.CurrencyRateProvider.create(
            {
                "service": "XE",
                # Test a daily increment, not the initial historical catch-up.
                "last_successful_run": cls.today - timedelta(days=1),
                "next_run": cls.today,
                "currency_ids": [
                    (4, cls.usd_currency.id),
                    (4, cls.eur_currency.id),
                ],
            }
        )
        cls.CurrencyRate.search([]).unlink()

    def setUp(self):
        super().setUp()
        response = Response()
        response.status_code = 200
        response._content = b"""<html><table><tbody><tr>
            <th scope="row"><a href="/currency/usd-us-dollar/">USD</a></th>
            <td>US Dollar</td><td>1.25</td><td>0.8</td>
            </tr></tbody></table></html>"""
        request = patch.object(
            type(self.xe_provider), "_request_data", return_value=response
        )
        request.start()
        self.addCleanup(request.stop)

    def test_cron(self):
        self.xe_provider._scheduled_update()
        rates = self.CurrencyRate.search([])
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates.currency_id, self.usd_currency)
        self.assertAlmostEqual(rates.rate, 1.25)

    def test_wizard(self):
        wizard = (
            self.env["res.currency.rate.update.wizard"]
            .with_context(default_provider_ids=[(6, False, self.xe_provider.ids)])
            .create({})
        )
        wizard.action_update()
        rates = self.CurrencyRate.search([])
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates.currency_id, self.usd_currency)
        self.assertAlmostEqual(rates.rate, 1.25)

    def test_missing_table_is_reported(self):
        response = Response()
        response._content = b"<html><p>No currency table</p></html>"
        with self.assertRaises(UserError):
            self.xe_provider._parse_data(response, ["USD"])
