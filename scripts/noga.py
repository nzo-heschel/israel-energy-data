from urllib.request import urlopen
import json
import logging

FORMAT = '%(asctime)s  %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)

noga_url = 'https://www.noga-iso.co.il/Umbraco/Api/Documents/GetCosts/?startDateString={}&endDateString={}&culture=he-IL&dataType=SMP'
SMP_CONST = "constrained"
SMP_UNCONST = "unconstrained"


def smp(start_date, end_date):
    logging.info("Request noga/smp data from %s to %s", start_date, end_date)
    response = urlopen(noga_url.format(start_date, end_date))
    logging.info("Received noga/smp data received")
    # Convert bytes to string type and string type to dict
    string = response.read().decode('utf-8')
    json_list = json.loads(string)
    total_constrained_smp = {}
    total_unconstrained_smp = {}
    for json_obj in json_list:
        date = json_obj["Date"]
        total_constrained_smp[date] = total_constrained_smp.get(date, 0) + json_obj["ConstrainedSmp"] * 0.5
        total_unconstrained_smp[date] = total_unconstrained_smp.get(date, 0) + json_obj["UnconstrainedSmp"] * 0.5
    return {SMP_CONST: total_constrained_smp, SMP_UNCONST: total_unconstrained_smp}
