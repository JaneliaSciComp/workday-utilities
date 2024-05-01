#!/usr/bin/env python
import argparse
import json
import sys
import colorlog
import requests
from tqdm import tqdm

# Configuration
CONFIG = {'config': {'url': 'http://config.int.janelia.org/'}}
# General
count = {'insert': 0, 'update': 0}
translate = {'EMPLOYEEID': 'id',
             'PREFERREDFIRSTNAME': 'first',
             'PREFERREDLASTNAME': 'last',
             'EMAILADDRESS': 'email',
             'PHONE1': 'phone',
             'LOCATIONNAME': 'location',
             'BUILDING': 'building',
             'WORKSPACE_NAME': 'workspace',
             'COSTCENTER': 'cost_center',
             'SUBROLLUP_GROUP': 'rollup_group',
             'TEAMCODE': 'team',
             'SUPORGNAME': 'organization',
             'JOBTITLE': 'title',
             'BUSINESSTITLE': 'business_title',
             'DEPARTMENTADDRESS1': 'address',
             'DEPARTMENTADDRESS2': 'address2',
             'DEPARTMENTADDRESS3': 'address3',
             'DEPARTMENTCOUNTRY': 'country',
             'DEPARTMENTCITY': 'city',
             'DEPARTMENTSTATE': 'state',
             'DEPARTMENTPOSTALCD': 'zip',
             'ACTIVEFLAG': 'active',
}


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


def initialize_program():
    """ Get REST configuration
    """
    global CONFIG
    data = call_responder('config', 'config/rest_services')
    CONFIG = data['config']


def post_change(ddict, userid='', configuration='workday'):
    if userid:
        suffix = '/' + userid
    else:
        suffix = ''
    endpoint = 'importjson/' + configuration + suffix
    resp = requests.post(CONFIG['config']['url'] + endpoint,
                         {"config": json.dumps(ddict)})
    if resp.status_code != 200:
        LOGGER.error(resp.json()['rest']['message'])
    else:
        rest = resp.json()
        if 'inserted' in rest['rest']:
            count['insert'] += rest['rest']['inserted']
        elif 'updated' in rest['rest']:
            count['update'] += rest['rest']['updated']


def update_users():
    known = call_responder('config', 'config/workday')
    LOGGER.info(f"Found {len(known['config']):,} entries in configuration")
    workday = call_responder('hhmi-services', 'IT/WD-hcm/wdworkerdetails')
    LOGGER.info(f"Found {len(workday):,} entries in Workday")
    ddict = dict()
    sorted_workday = sorted(workday, key=lambda k: k['WORKERUSERID'])
    in_workday = {}
    for r in tqdm(sorted_workday):
        user = dict()
        userid = r["WORKERUSERID"].lower()
        in_workday[userid] = True
        if userid not in known['config']:
            LOGGER.info("%s is a new user", (userid))
        user['manager_userid'] = r['MANAGERUSERID'].lower()
        missing = False
        for key, val in translate.items():
            if key not in r:
                LOGGER.error(f"Missing {key}")
                print(json.dumps(r, indent=2))
                missing = True
                break
            user[val] = r[key]
        if missing:
            continue
        ddict[userid] = user
        if ARG.QUICK and userid in known['config']:
            continue
        LOGGER.debug(user)
        if not ARG.REBUILD:
            post_change(user, userid)
    LOGGER.info(f"Found {len(ddict):,} active entries")
    if ARG.BACKCHECK:
        for key, val in tqdm(known['config'].items()):
            if key not in in_workday and 'active' in val and val['active'] == 'Y':
                LOGGER.warning(f"{key} is in config but not in Workday")
                val['active'] = 'N'
                post_change(val, key)
    if ARG.REBUILD:
        LOGGER.info(f"Workday config will contain {len(ddict):,} Janelia entries")
        post_change(ddict)


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(
        description='Update Workday user Configuration')
    PARSER.add_argument('--quick', action='store_true', dest='QUICK',
                        default=False, help='Only process new entries')
    PARSER.add_argument('--backcheck', action='store_true', dest='BACKCHECK',
                        default=False, help='Backcheck to Workday')
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

    initialize_program()
    update_users()
    print(f"Documents inserted in config database: {count['insert']:,}")
    print(f"Documents updated in config database: {count['update']:,}")

