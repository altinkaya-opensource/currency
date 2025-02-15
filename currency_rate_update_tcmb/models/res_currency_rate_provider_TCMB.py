# Copyright 2023 Yiğit Budak (https://github.com/yibudak)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from datetime import date, timedelta

import requests
from lxml.etree import fromstring

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


TCMB_RATE_TYPES = [
    "ForexBuying",
    "ForexSelling",
    "BanknoteBuying",
    "BanknoteSelling",
]


class ResCurrencyRateProviderTCMB(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("TCMB", "Central Bank of the Republic of Turkey")],
        ondelete={"TCMB": "set default"},
    )
    service_rate_type = fields.Selection(
        [
            ("ForexBuying", "Forex Buy"),
            ("ForexSelling", "Forex Sell"),
            ("BanknoteBuying", "Banknote Buy"),
            ("BanknoteSelling", "Banknote Sell"),
        ],
        string="TCMB Rate Type",
        default="ForexBuying",
        required=True,
    )

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != "TCMB":
            return super()._get_supported_currencies()

        # List of currencies obrained from:
        # http://www.tcmb.gov.tr/kurlar/today.xml
        return [
            "USD",
            "AUD",
            "DKK",
            "EUR",
            "GBP",
            "CHF",
            "SEK",
            "CAD",
            "KWD",
            "NOK",
            "SAR",
            "JPY",
            "BGN",
            "RON",
            "RUB",
            "IRR",
            "CNY",
            "PKR",
            "QAR",
            "XDR",
            "TRY",
        ]

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "TCMB":
            return super()._obtain_rates(base_currency, currencies, date_from, date_to)

        invert_calculation = False
        if base_currency != "TRY":
            invert_calculation = True
            if base_currency not in currencies:
                currencies.append(base_currency)

        if "TRY" in currencies:
            currencies.remove("TRY")

        def daterange(start_date, end_date):
            for n in range(int((end_date - start_date).days)):
                yield start_date + timedelta(n)

        result = {}
        if date_from == date_to and date_from == date.today():
            url = "https://www.tcmb.gov.tr/kurlar/today.xml"
            try:
                rate_date = date.today().strftime("%Y-%m-%d")
                currency_data = self.get_tcmb_currency_data(url, currencies)
                result[rate_date] = currency_data
            except Exception:
                _logger.error(
                    _("No currency rate on %s") % date_from.strftime("%Y-%m-%d")
                )
        else:
            for single_date in daterange(date_from, date_to):
                year = str(single_date.year)
                month = "{:02d}".format(single_date.month)
                day = "{:02d}".format(single_date.day)
                url = "https://www.tcmb.gov.tr/kurlar/%s%s/%s%s%s.xml" % (
                    year,
                    month,
                    day,
                    month,
                    year,
                )
                try:
                    rate_date = single_date.strftime("%Y-%m-%d")
                    currency_data = self.get_tcmb_currency_data(url, currencies)
                    result[rate_date] = currency_data
                except Exception:
                    _logger.error(
                        _("No currency rate on %s") % single_date.strftime("%Y-%m-%d")
                    )
                    continue

        content = result
        if invert_calculation:
            for k in content.keys():
                base_rate = float(content[k][base_currency])
                for rate in content[k].keys():
                    content[k][rate] = str(float(content[k][rate]) / base_rate)
                content[k]["TRY"] = str(1.0 / base_rate)
        return content

    def rate_retrieve(self, dom, currency, rate_type):
        res = {}
        xpath_currency_rate = "./Currency[@Kod='%s']/%s" % (currency.upper(), rate_type)
        res["rate_currency"] = float(dom.findall(xpath_currency_rate)[0].text)
        xpath_rate_ref = "./Currency[@Kod='%s']/Unit" % currency.upper()
        res["rate_ref"] = float(dom.findall(xpath_rate_ref)[0].text)
        return res

    def get_tcmb_currency_data(self, url, currencies):
        response = requests.get(url).text
        dom = fromstring(response.encode("utf-8"))

        _logger.debug("TCMB sent a valid XML file")
        currency_data = {}
        for currency in currencies:
            currency_data[currency] = {}
            for rate_type in TCMB_RATE_TYPES:
                try:
                    curr_data = self.rate_retrieve(dom, currency, rate_type)
                except TypeError:  # This means that the currency type is not exist in the currency list
                    curr_data = {"rate_ref": 1.0, "rate_currency": 1.0}
                currency_data[currency][rate_type] = curr_data["rate_ref"] / (
                    curr_data["rate_currency"] or 1.0
                )

        return currency_data
