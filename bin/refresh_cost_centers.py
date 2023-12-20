#!/usr/bin/env python
import argparse
import json
import sys
import colorlog
import requests

# Configuration
CONFIG = {'config': {'url': 'http://config.int.janelia.org/'}}
# General
count = {'insert': 0, 'update': 0}


def call_responder(server, endpoint):
    url = CONFIG[server]['url'] + endpoint
    try:
        req = requests.get(url)
    except requests.exceptions.RequestException as err:
        LOGGER.critical(err)
        sys.exit(-1)
    if req.status_code != 200:
        LOGGER.error('Status: %s', str(req.status_code))
        sys.exit(-1)
    return req.json()


def post_change(ddict, userid='', configuration='cost_centers'):
    if userid:
        suffix = '/' + userid
    else:
        suffix = ''
    endpoint = 'importjson/' + configuration + suffix
    resp = requests.post(CONFIG['config']['url'] + endpoint,
                         {"config": json.dumps(ddict),
                          "definition": "Cost centers"})
    if resp.status_code != 200:
            LOGGER.error(resp.json()['rest']['message'])
    else:
        rest = resp.json()
        if 'inserted' in rest['rest']:
            count['insert'] += rest['rest']['inserted']
        elif 'updated' in rest['rest']:
            count['update'] += rest['rest']['updated']


def update_cost_centers(rebuild):
    known = call_responder('config', 'config/cost_centers')
    LOGGER.info("Found %d entries in existing configuration" % len(known['config']))
    data = call_responder('hhmi-services', 'IT/WD-hcm/locations')
    LOGGER.info("Found %d locations" % len(data['data']))
    location = dict()
    for loc in data['data']:
        location[loc['LocationCode']] = loc
    LOGGER.info("Saved %d locations" % len(location))
    data = call_responder('hhmi-services', 'IT/WD-fin/lookups/costcenters')
    LOGGER.info("Found %d cost centers" % len(data['data']))
    ccdict = dict()
    for cc in data['data']:
        if cc['DefaultLocationID'] not in location:
            LOGGER.error("Could not find %s in saveld locations", cc['DefaultLocationID'])
            continue
        loc = location[cc['DefaultLocationID']]
        ccdict[cc['CostCenter']] = {"organization": cc['CCDescr'],
                                    "status": cc['Status'],
                                    "location": cc['DefaultLocationName'],
                                    "address": loc['PrimaryAddressLine1'],
                                    "city": loc['City'],
                                    "state": loc['State'],
                                    "zip": loc['PostalCode'],
                                    "country": loc['Country']
                                   }
        LOGGER.debug(ccdict[cc['CostCenter']])
        if 'PrimaryAddressLine2' in loc:
            ccdict[cc['CostCenter']]['address2'] = loc['PrimaryAddressLine2']
    LOGGER.info("Updated %d cost centers" % len(ccdict))
    post_change(ccdict)


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(
        description='Update Workday user Configuration')
    PARSER.add_argument('--rebuild', action='store_true', dest='REBUILD',
                        default=False, help='Rebuild config from scratch')
    PARSER.add_argument('--verbose', action='store_true', dest='VERBOSE',
                        default=False, help='Turn on verbose output')
    PARSER.add_argument('--debug', action='store_true', dest='DEBUG',
                        default=False, help='Turn on debug output')
    ARG = PARSER.parse_args()

    LOGGER = colorlog.getLogger()
    ATTR = colorlog.colorlog.logging if "colorlog" in dir(colorlog) else colorlog
    if ARG.DEBUG:
        LOGGER.setLevel(ATTR.DEBUG)
    elif ARG.VERBOSE:
        LOGGER.setLevel(ATTR.INFO)
    else:
        LOGGER.setLevel(ATTR.WARNING)
    HANDLER = colorlog.StreamHandler()
    HANDLER.setFormatter(colorlog.ColoredFormatter())
    LOGGER.addHandler(HANDLER)

    CONFIG = call_responder('config', 'config/rest_services')['config']
    update_cost_centers(ARG.REBUILD)
    print("Documents inserted in config database: %d" % count['insert'])
    print("Documents updated in config database: %d" % count['update'])

