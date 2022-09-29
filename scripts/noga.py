import json
import logging
import requests
import os
import datetime
from dateutil.relativedelta import relativedelta

noga_url = 'https://www.noga-iso.co.il/Umbraco/Api/Documents/GetCosts/?startDateString={}&endDateString={}&culture=he-IL&dataType={}'
SMP_CONST = "ConstrainedSmp"
SMP_UNCONST = "UnconstrainedSmp"

COST_AVERAGE = "AverageCost"
COST_COST = "Cost"
COST_REN = "RenewableGen"
COST_CONV = "ConventionalGen"
COST_DEMAND = "SystemDemand"

FORECAST_REN = "Renewable"
FORECAST_DEMAND = "SystemDemand"

FIRST_DATE = "01-01-2010"

proxies = {
    'https': os.environ.get('PROXY_SERVER'),
}


def update(store, noga_type, start_date, end_date):
    noga_types = NOGA_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA_TYPE_MAPPING
    # TODO: error handling wrong noga_type
    result = {}
    for a_type in noga_types:
        namespace = "noga." + a_type
        start_date = start_date or store.latest_date(namespace) or "01-01-2000"
        json_list = request(a_type, start_date, end_date)
        result[namespace] = json_list
    values = []
    count = 0
    total_count = 0
    for namespace in result:
        for entry in result.get(namespace):
            date0 = entry.get("Date")
            date = date0.replace("/", "-")
            time = entry.get("Time")
            for tag in [key for key in entry.keys() if key not in ["Date", "Time"]]:
                values.append((namespace, date, time[0:5], tag, entry.get(tag)))
                count = count + 1
                total_count = total_count + 1
                if count > 100:
                    store.bulk_insert(values)
                    values = []
                    count = 0
    if values:
        store.bulk_insert(values)
    logging.info("Inserted %s values into storage", total_count)


def get(store, noga_type, start_date, end_date, tag, time="hour"):
    noga_types = NOGA_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA_TYPE_MAPPING
    start_date = start_date or one_month_ago()
    logging.info("Retrieving noga data with type(s) %s from %s until %s with \"%s\" interval and tag \"%s\"",
                 ", ".join(noga_types), start_date, end_date, time, tag)
    result = {}
    for a_type in noga_types:
        data = store.retrieve_range("noga." + a_type, start_date, end_date, time=time, tag=tag)
        result.update(data)
    return result


def one_month_ago():
    date = datetime.date.today() + relativedelta(months=-1)
    return date.strftime("%d-%m-%Y")


NOGA_TYPE_MAPPING = {
    'smp': 'SMP',
    'cost': 'Cost',
    'forecast1': 'DemandForecast&forecastType=1',
    'forecast2': 'DemandForecast&forecastType=2'
}


def request(noga_type, start_date, end_date):
    logging.info("Request noga/%s data from %s to %s", noga_type, start_date, end_date)
    data_type = NOGA_TYPE_MAPPING.get(noga_type)
    if data_type is None:
        return {"error": "Unrecognized Noga type"}
    start_date = start_date.replace("-", "/")
    end_date = end_date.replace("-", "/")
    logging.info(noga_url.format(start_date, end_date, data_type))
    response = requests.get(noga_url.format(start_date, end_date, data_type), proxies=proxies)
    # response = urlopen(noga_url.format(start_date, end_date))
    logging.info("Received noga.%s data with status code %s", noga_type, response.status_code)
    if response.status_code >= 400:
        raise ValueError(response.reason, json.loads(response.content)["Message"])
    # Convert bytes to string type and string type to dict
    string = response.content.decode('utf-8')
    json_list = json.loads(string)
    logging.info("Received %s values for noga.%s", len(json_list), noga_type)
    return json_list
