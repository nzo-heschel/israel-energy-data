import json
import logging
import tempfile
import urllib.request
import pandas as pd
import re
import os
import datetime
from dateutil.relativedelta import relativedelta
import noga_labels
import noga_tokens

SMP_CONST = "ConstrainedSmp"
SMP_UNCONST = "UnconstrainedSmp"

COST_AVERAGE = "AverageCost"
COST_COST = "Cost"
COST_REN = "RenewableGen"
COST_CONV = "ConventionalGen"
COST_DEMAND = "SystemDemand"

FORECAST_REN = "Renewable"
FORECAST_DEMAND = "SystemDemand"

proxies = {
    'https': os.environ.get('PROXY_SERVER'),
}


class NogaType:
    def __init__(self, path, token, start_date="01-01-2020", dict_key=None):
        self.path = path
        self.token = token
        self.start_date = start_date
        self.dict_key = dict_key


def update(store, noga_type, start_date, end_date):
    """
    Collects data from NOGA API endpoints and stores it in the database.
    Handles individual endpoint failures to prevent data loss and ensure
    continuation of data collection for other endpoints.

    Args:
        store: Db where to store the results
        noga_type (str): The specific NOGA2 type to fetch, or "all" for all types.
        start_date (str): The start date for data collection (YYYY-MM-DD format).
        end_date (str): The end date for data collection (YYYY-MM-DD format).

    Returns:
        str: A message indicating the total number of values inserted into storage.
    """
    noga2_types = NOGA2_TYPE_MAPPING if noga_type == "all" else ([noga_type] if noga_type else list(NOGA2_TYPE_MAPPING.keys()))

    total_inserted_count = 0
    failed_endpoints_details = {}
    all_new_keys = {}

    for a_type in noga2_types:
        namespace = "noga2." + a_type
        ns_start_date = start_date or store.latest_date(namespace) or NOGA2_TYPE_MAPPING.get(a_type, {}).get("start_date")

        if not ns_start_date:
            logging.warning(f"Skipping {namespace}: Could not determine a start date for data collection.")
            failed_endpoints_details[namespace] = "Could not determine a start date"
            continue

        try:
            logging.info(f"Attempting to request data for {namespace} from {ns_start_date} to {end_date}")
            json_list, new_keys = request_data(a_type, ns_start_date, end_date)
            # Store results immediately after successful collection for this endpoint
            if json_list:
                current_endpoint_results = {namespace: json_list}
                count = store_results(store, current_endpoint_results)
                total_inserted_count += count
                logging.info(f"Successfully inserted {count} values for {namespace}.")
            else:
                logging.info(f"No new data found for {namespace} in the specified range.")
                failed_endpoints_details[namespace] = "No new data"
            if new_keys:
                all_new_keys[namespace] = new_keys

        except Exception as e:
            # Log the error but continue with the next endpoint
            logging.error(f"Failed to collect data for endpoint '{namespace}': {e}", exc_info=True)
            failed_endpoints_details[namespace] = str(e)
            # Data for this specific endpoint is lost, but previous successful collections are preserved
            # and subsequent collections will still be attempted.

    return_message = f"Inserted {total_inserted_count} values into storage."
    if failed_endpoints_details:
        for namespace, reason in failed_endpoints_details.items():
            return_message += f"\n{namespace} failed with reason '{reason}'."
    if all_new_keys:
        return_message += f"\nNew keys: {all_new_keys}."
    return return_message

def store_results(store, result):
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
                match = re.match(r'-?[0-9.]+', str(entry.get(tag)).strip())
                val = match.group(0)
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
    return total_count


def upload(store, f):
    # Only supports uploading files with titles in Hebrew
    xl_file = tempfile.NamedTemporaryFile()
    try:
        logging.debug("Saving file %s locally as %s", f.filename, xl_file.name)
        f.save(xl_file.name)
        logging.debug("Reading local file %s", xl_file.name)
        df = pd.read_excel(xl_file.name, header=1)
        logging.debug("Done reading local file %s", xl_file.name)
        labels = df.columns.values.tolist()
        logging.info("Labels in file: %s", labels)
        namespace, new_labels = noga_labels.new_labels(labels)
        logging.info("Namespace for %s is %s", f.filename, namespace)
        df.columns = new_labels  # rename columns
        if isinstance(df['Time'][1], datetime.time):
            df['Time'] = df['Time'].apply(lambda x: str(x))
        if isinstance(df['Date'][1], datetime.datetime):
            df['Date'] = df['Date'].apply(lambda x: x.strftime('%d-%m-%Y'))
    except ValueError as ve:
        logging.error("Error: " + str(ve))
        return {"failure": str(ve)}
    finally:
        xl_file.close()
    json_list = df_to_json(df)
    result = {namespace: json_list}
    count = store_results(store, result)
    return {"success": True, "count": count}


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
    noga_labels.SMP: NogaType('SMP/SMPAPI/v1', noga_tokens.SMP_TOKEN, "27-12-2021"),
    noga_labels.ENERGY: NogaType('PRODUCTIONMIX/PRODMIXAPI/v1', noga_tokens.PRODMIX_TOKEN, "05-03-2023", "energy"),
    noga_labels.SYSTEM_DEMAND: NogaType('DEMAND/DEMANDAPI/v1', noga_tokens.DEMAND_TOKEN, "27-12-2022"),
    noga_labels.CO2_EMISSION: NogaType('CO2/CO2API/v1', noga_tokens.CO2_TOKEN, "23-03-2023", "co2"),
}


def date_ordinal(date_str):
    return datetime.datetime.strptime(date_str, "%d/%m/%Y").toordinal()


def date_str(date_ordinal):
    return datetime.datetime.fromordinal(date_ordinal).strftime("%d/%m/%Y")


def extract_values_from_post_response(jsons, mapping):
    values = []
    new_keys_logged = set()
    for day_item in jsons:
        date = day_item['date']
        time_items_key = next(k for k in day_item if k != 'date')
        time_items = day_item[time_items_key]
        for time_item in time_items:
            value = {'Date': date}
            for k, v in time_item.items():
                try:
                    mapped_key = mapping[k]
                    value[camel_no_unit(mapped_key)] = v
                except KeyError:
                    if k not in new_keys_logged:
                        logging.error("New key '%s' in noga2 response", k)
                        new_keys_logged.add(k)
                    continue
            values.append(value)
    return values, new_keys_logged

def request_data(noga_type, start_date, end_date):
    data_type = NOGA2_TYPE_MAPPING.get(noga_type)
    logging.info("Request noga2.%s data from %s to %s using HTTP POST",
                 noga_type, start_date, end_date)
    if data_type is None:
        return {"error": "Unrecognized Noga type"}
    jsons = noga_post(data_type.path, start_date, end_date, data_type.token)
    jsons = jsons[data_type.dict_key] if data_type.dict_key else jsons
    label_mapping = noga_labels.NS_LABEL_POST_MAP[noga_type]
    json_list, new_keys = extract_values_from_post_response(jsons, label_mapping)
    logging.info("Received %s values for noga2.%s", len(json_list), noga_type)
    return json_list, new_keys


POST_URL = "https://apim-api.noga-iso.co.il/"


def noga_post(path, from_date, to_date, token):
    hdr = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Ocp-Apim-Subscription-Key': noga_tokens.decrypt_token(token, noga_tokens.NOGA_KEY)
    }
    data = json.dumps({"fromDate": from_date, "toDate": to_date})
    req = urllib.request.Request(POST_URL + path, headers=hdr, data=bytes(data.encode("utf-8")))
    req.get_method = lambda: 'POST'
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode("utf-8"))


def df_to_json(df):
    labels = df.columns.values.tolist()
    logging.info("Labels: %s", labels)
    df.drop(columns=[label for label in labels if label[:7] == "Unnamed"], inplace=True)
    labels = df.columns.values.tolist()
    new_labels = [camel_no_unit(label) for label in labels]
    logging.info("New labels: %s", new_labels)
    df.columns = new_labels  # rename columns
    count_before = len(df.index)
    df.drop_duplicates(inplace=True)
    count_after = len(df.index)
    if count_after < count_before:
        logging.info("Dropped duplicates. Before: %s. After: %s.", count_before, count_after)
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
