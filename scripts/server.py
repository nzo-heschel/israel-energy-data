import datetime
import json
import logging
import os
from dateutil.relativedelta import relativedelta
import http.client
import scripts.noga as noga
import scripts.storage.storage_util as storage
from flask import Flask, render_template, request
import pandas as pd

PORT = int(os.environ.get("PORT", 9999))
SMP_DATE_FORMAT = "%d-%m-%Y"
STORAGE_URI = os.environ.get('STORAGE_URI', "mysql://root:mysql_root_123@localhost:3306")
store = storage.new_instance(STORAGE_URI)

app = Flask(__name__, template_folder='../resources')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/update')
def update():
    try:
        source, data_type, start_date, end_date = query_variables(request.args)[0:4]
        if source == "noga2" or source == "all":
            response = noga.update(store, noga_type=data_type, start_date=start_date, end_date=end_date)
    except Exception as ex:
        logging.exception("Error: %s", ex)
        return "Error: {}".format(ex), 400
    return response, 200


@app.route('/upload', methods=['GET'])
def upload_get():
    return render_template("upload.html")


@app.route('/upload/<source>', methods=['POST'])
def upload_post(source):
    # curl command example:
    # curl -F 'file=@/Users/foo/Downloads/Energy_07_08_2023-07_08_2023.xlsx' localhost:9999/upload/noga
    agent = request.environ['HTTP_USER_AGENT']
    agent_short_name = agent.split(" ")[0]
    f = request.files['file']
    logging.info("Agent %s request to upload file %s with source %s",
                 agent_short_name, f.filename, source)
    result = {}
    if source == "noga":
        result = noga.upload(store, f)

    curl = agent_short_name.startswith("curl")
    if "success" in result:
        if curl:
            return "FIle {} uploaded successfully, {} values stored\n".format(f.filename, result["count"])
        else:
            return render_template("success.html", name=f.filename, count=result["count"])
    else:
        if curl:
            return "File upload failed, {}\n".format(result["failure"])
        else:
            return render_template("failure.html", message=result["failure"])


@app.route('/success', methods=['POST'])
def success():
    if request.method == 'POST':
        source = request.values['source']
        return upload_post(source)


@app.route('/get')
def get():
    try:
        source, data_type, start_date, end_date, tag, result_format, time = query_variables(request.args)
        data = {}
        if source == "noga" or source == "noga2":
            data = noga.get(store, source, noga_type=data_type, start_date=start_date,
                            end_date=end_date, tag=tag, time=time)
        formatted_data = format_data(data, result_format)
        return formatted_data
    except Exception as ex:
        logging.exception("Error: %s", ex)
        return "Error: {}".format(ex), 400


def format_data(data, result_format):
    match result_format:
        case "html":
            return json_to_df(data).fillna('').to_html(index=False)
        case "csv":
            return app.response_class(
                response=json_to_df(data).to_csv(index=False, sep=","),
                status=200,
                mimetype='text/plain'
            )
        case "tsv":
            return app.response_class(
                response=json_to_df(data).to_csv(index=False, sep="\t"),
                status=200,
                mimetype='text/plain'
            )
    # default format: json
    return app.response_class(
        response=json.dumps(data, indent=2),
        status=200,
        mimetype='application/json'
    )


def json_to_df(json_data):
    results = []
    for namespace, v1 in json_data.items():
        for date, v2 in v1.items():
            for time, tag_value_pairs in v2.items():
                line = {"type": namespace, "date": date, "time": time}
                line.update(tag_value_pairs)
                results.append(line)
    return pd.DataFrame(results)


def default_dates():
    today = datetime.date.today()
    start_time = today + relativedelta(months=-1)
    end = today.strftime(SMP_DATE_FORMAT)
    start = start_time.strftime(SMP_DATE_FORMAT)
    return start, end


def query_variables(args):
    source = args.get('source', "all")
    data_type = args.get('type', "all")
    start_date = args.get('start_date')
    end_date = args.get('end_date', default_dates()[1])  # today
    result_format = args.get('format', "json")
    time = args.get('time', "hour")
    tag = args.get('tag')
    return source, data_type, start_date, end_date, tag, result_format, time


def http_debug_level(level):
    http.client.HTTPConnection.debuglevel = level
    # logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def main():
    FORMAT = '%(asctime)s [%(levelname)s] : %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    http_debug_level(1)
    logging.info("Starting")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
