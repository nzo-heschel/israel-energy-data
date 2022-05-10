import json
import logging
import requests
import http.client
import os

noga_url = 'https://www.noga-iso.co.il/Umbraco/Api/Documents/GetCosts/?startDateString={}&endDateString={}&culture=he-IL&dataType={}'
SMP_CONST = "constrained"
SMP_UNCONST = "unconstrained"

COST_AVERAGE = "AverageCost"
COST_REN = "Renewable"
COST_CONV = "Conventional"
COST_DEMAND = "Demand"

FORMAT = '%(asctime)s  %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)

proxies = {
    'https': os.environ.get('PROXY_SERVER'),
}


def http_debug_level(level):
    http.client.HTTPConnection.debuglevel = level
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


NOGA_TYPE_MAPPING = {
    'smp': 'SMP',
    'cost': 'Cost',
    'forecast1': 'DemandForecast&forecastType=1',
    'forecast2': 'DemandForecast&forecastType=2'
}


def smp(start_date, end_date):
    smp_json_list = request('smp', start_date, end_date)
    if is_error(smp_json_list):
        return smp_json_list
    total_constrained_smp = {}
    total_unconstrained_smp = {}
    for json_obj in smp_json_list:
        date = json_obj["Date"]
        total_constrained_smp[date] = total_constrained_smp.get(date, 0) + json_obj["ConstrainedSmp"] * 0.5
        total_unconstrained_smp[date] = total_unconstrained_smp.get(date, 0) + json_obj["UnconstrainedSmp"] * 0.5
    return {SMP_CONST: total_constrained_smp, SMP_UNCONST: total_unconstrained_smp}


def cost(start_date, end_date):
    cost_json_list = request('cost', start_date, end_date)
    if is_error(cost_json_list):
        return cost_json_list
    average_cost = {}
    total_renewable_gen = {}
    total_conventional_gen = {}
    total_system_demand = {}
    for json_obj in cost_json_list:
        date = json_obj["Date"]
        average_cost[date] = average_cost.get(date, 0) + json_obj["Cost"] / 48
        total_renewable_gen[date] = total_renewable_gen.get(date, 0) + json_obj["RenewableGen"] / 1000
        total_conventional_gen[date] = total_conventional_gen.get(date, 0) + json_obj["ConventionalGen"] / 1000
        total_system_demand[date] = total_system_demand.get(date, 0) + json_obj["SystemDemand"] / 1000
    return {COST_AVERAGE: average_cost,
            COST_REN: total_renewable_gen,
            COST_CONV: total_conventional_gen,
            COST_DEMAND: total_system_demand}


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
    logging.info("Received noga/%s data with status code %s", noga_type, response.status_code)
    if response.status_code >= 400:
        logging.warning("Error: %s", response.reason)
        return {"error": response.reason}
    # Convert bytes to string type and string type to dict
    string = response.content.decode('utf-8')
    json_list = json.loads(string)
    return json_list


def is_error(json_list):
    return type(json_list) is dict and json_list.get("error")


http_debug_level(1)
# print(smp("01/01/2020", "31/01/2022"))
