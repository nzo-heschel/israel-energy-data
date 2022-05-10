import json
import logging
import requests
import http.client
import os

noga_url = 'https://www.noga-iso.co.il/Umbraco/Api/Documents/GetCosts/?startDateString={}&endDateString={}&culture=he-IL&dataType=SMP'
SMP_CONST = "constrained"
SMP_UNCONST = "unconstrained"

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


def smp(start_date, end_date):
    logging.info("Request noga/smp data from %s to %s", start_date, end_date)
    logging.info(noga_url.format(start_date, end_date))
    response = requests.get(noga_url.format(start_date, end_date), proxies=proxies)
    # response = urlopen(noga_url.format(start_date, end_date))
    logging.info("Received noga/smp data with status code %s", response.status_code)
    if response.status_code >= 400:
        logging.warning("Error: %s", response.reason)
        return {"error": response.reason}
    # Convert bytes to string type and string type to dict
    string = response.content.decode('utf-8')
    json_list = json.loads(string)
    total_constrained_smp = {}
    total_unconstrained_smp = {}
    for json_obj in json_list:
        date = json_obj["Date"]
        total_constrained_smp[date] = total_constrained_smp.get(date, 0) + json_obj["ConstrainedSmp"] * 0.5
        total_unconstrained_smp[date] = total_unconstrained_smp.get(date, 0) + json_obj["UnconstrainedSmp"] * 0.5
    return {SMP_CONST: total_constrained_smp, SMP_UNCONST: total_unconstrained_smp}

http_debug_level(5)
print(smp("01/01/2020", "04/05/2022"))
