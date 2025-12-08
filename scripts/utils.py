import logging
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import msgpack
import json
import time

def retrieve_url(url):
    result = None
    retry = 1
    while True:
        retry += 1
        try:
            logging.info("Executing URL call: " + url)
            with urlopen(url) as response:
                content_type = response.info().get('Content-Type', '')
                if content_type == "application/x-msgpack":
                    result = msgpack.unpackb(response.read(), raw=False)
                else:
                    data = response.read().decode('utf-8')
                    result = json.loads(data)
            break
        except (HTTPError, URLError) as ex:
            logging.warning("Exception while trying to get data: " + str(ex))
            logging.warning("Retry #{} in 2 seconds".format(retry))
            time.sleep(2)
    if not result:
        logging.error("Could not get data from server")
        return None
    return result