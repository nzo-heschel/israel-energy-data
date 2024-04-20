import logging
import tempfile
import time
import urllib.request
import pandas as pd
import re
import urllib.request
import os
import datetime
from dateutil.relativedelta import relativedelta
from urllib.error import HTTPError

noga_file_url = 'https://www.noga-iso.co.il/Umbraco/Surface/Export/ExportCost/' \
                '?startDateString={}&endDateString={}&culture=en-US&dataType={}'
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
MAX_DAYS_PER_REQUEST = 10

proxies = {
    'https': os.environ.get('PROXY_SERVER'),
}


class NogaType:
    def __init__(self, data_type, start_date="01-01-2020", chunk_size=30):
        self.data_type = data_type
        self.start_date = start_date
        self.chunk_size = chunk_size


def update(store, noga_type, start_date, end_date):
    # Update old noga url (namespace noga.*) is no longer supported, only noga2.* with file API is supported.
    noga2_types = NOGA2_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA2_TYPE_MAPPING
    # TODO: error handling wrong noga_type
    result = {}
    for a_type in noga2_types:
        namespace = "noga2." + a_type
        ns_start_date = start_date or store.latest_date(namespace) or NOGA2_TYPE_MAPPING.get(a_type).start_date
        json_list = request_file(a_type, ns_start_date, end_date)
        result[namespace] = json_list
    values = []
    count = 0
    total_count = 0
    for namespace in result:
        for entry in result.get(namespace):
            date0 = entry.get("Date")
            date = date0.replace("/", "-")
            time = entry.get("Time")
            for tag in [key for key in entry.keys()
                        if key not in ["Date", "Time", "FileDate", "IsOnBlobList"] and entry.get(key) != "-"]:
                val = re.sub(r'[^0-9.]', '', str(entry.get(tag)).strip())
                if val == '':
                    continue
                values.append((namespace, date, time[0:5], tag, val))
                count = count + 1
                total_count = total_count + 1
                if count > 100:
                    store.bulk_insert(values)
                    values = []
                    count = 0
    if values:
        store.bulk_insert(values)
    logging.info("Inserted %s values into storage", total_count)
    return "Inserted {} values into storage".format(total_count)


def get(store, source, noga_type, start_date, end_date, tag, time="hour"):
    noga_types = NOGA2_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA2_TYPE_MAPPING
    start_date = start_date or one_month_ago()
    logging.info("Retrieving %s data with type(s) %s from %s until %s with \"%s\" interval and tag \"%s\"",
                 source, ", ".join(noga_types), start_date, end_date, time, tag)
    result = {}
    for a_type in noga_types:
        data = store.retrieve_range(source + "." + a_type, start_date, end_date, time=time, tag=tag)
        result.update(data)
    for key in result:
        logging.info("Retrieved {} items of type {}".format(sum(len(v) for v in result[key].values()), key))
    return result


def one_month_ago():
    date = datetime.date.today() + relativedelta(months=-1)
    return date.strftime("%d-%m-%Y")


NOGA2_TYPE_MAPPING = {
    'smp': NogaType('SMP', "27-12-2021"),
    'cost': NogaType('Cost', "15-12-2021"),
    'forecast1': NogaType('DemandForecast&forecastType=1', "26-10-2021"),
    'forecast2': NogaType('DemandForecast&forecastType=2', "25-10-2021"),
    'market': NogaType('DemandForecastNEW&forecastCategory=1', "27-12-2022"),
    'producer': NogaType('DemandForecastNEW&forecastCategory=2', "27-12-2022"),
    'reserve': NogaType('DemandForecastNEW&forecastCategory=3', "27-12-2022"),
    'energy': NogaType('DemandForecastNEW&forecastCategory=6', "05-03-2023", 5),
    'system_demand': NogaType('DemandForcastCurveGraph', "27-12-2022", 5),
    'co2emission': NogaType('CO2', "23-03-2023"),
}


def date_ordinal(date_str):
    return datetime.datetime.strptime(date_str, "%d/%m/%Y").toordinal()


def date_str(date_ordinal):
    return datetime.datetime.fromordinal(date_ordinal).strftime("%d/%m/%Y")


def daterange(from_date, to_date, step):
    from_date_ordinal = date_ordinal(from_date)
    to_date_ordinal = date_ordinal(to_date)
    for start_ordinal in range(from_date_ordinal, to_date_ordinal + 1, step + 1):
        end_ordinal = min(start_ordinal + step, to_date_ordinal)
        yield [date_str(start_ordinal), date_str(end_ordinal)]


def request_file(noga_type, start_date, end_date):
    data_type = NOGA2_TYPE_MAPPING.get(noga_type)
    logging.info("Request noga2.%s data from %s to %s in chunks of %s days",
                 noga_type, start_date, end_date, data_type.chunk_size)
    if data_type is None:
        return {"error": "Unrecognized Noga type"}
    start_date = start_date.replace("-", "/")
    end_date = end_date.replace("-", "/")
    json_list_all = []
    for start_date_1, end_date_1 in daterange(start_date, end_date, data_type.chunk_size):
        url = noga_file_url.format(start_date_1, end_date_1, data_type.data_type)
        logging.info(url)
        json_list = get_data_from_file(url)
        logging.info("Received %s values for noga2.%s", len(json_list), noga_type)
        json_list_all.extend(json_list)
    logging.info("Received total %s values for noga2.%s", len(json_list_all), noga_type)
    return json_list_all


def get_data_from_file(url):
    retry = 1
    while retry:
        xl_file = tempfile.NamedTemporaryFile()

        try:
            urllib.request.urlretrieve(url, xl_file.name)
            df = pd.read_excel(xl_file.name, header=1)
            retry = 0
        except ValueError as ve:
            if len(ve.args) == 1 and \
                    ve.args[0] == 'Excel file format cannot be determined, you must specify an engine manually.':
                return []
            else:
                raise ve
        except HTTPError as httpe:
            if httpe.getcode() == 403:
                logging.error(httpe)
                if retry < 4:
                    logging.info("SLEEPING")
                    time.sleep(10)
                    retry += 1
                    continue
            raise httpe
        except Exception as ex:
            raise ex
        finally:
            xl_file.close()

    labels = df.columns.values.tolist()
    logging.info("Labels: %s", labels)
    df.drop(columns=[label for label in labels if label[:7] == "Unnamed"], inplace=True)
    labels = df.columns.values.tolist()
    new_labels = [camel_no_unit(label) for label in labels]
    logging.info("New labels: %s", new_labels)
    df.columns = new_labels  # rename columns
    json_list = []
    for row in df.itertuples():
        json_row = {"Date": row.Date, "Time": row.Time}
        for i in range(2, len(labels)):
            json_row[new_labels[i]] = str(row[i+1])
        json_list.append(json_row)
    return json_list


pattern_units = re.compile(r" [\[(].*[\])]")


def camel_no_unit(s):
    s = pattern_units.sub("", s)
    s = s.title().replace(" ", "").replace("-", "")
    s = s.replace("Hour", "Time")
    return s
