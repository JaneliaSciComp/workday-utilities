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


def update_users(quick, rebuild):
    known = call_responder('config', 'config/workday')
    LOGGER.info("Found %d entries in configuration", len(known['config']))
    workday = call_responder('hhmi-services', 'IT/WD-hcm/wdworkerdetails')
    LOGGER.info("Found %d entries in Workday", len(workday))
    ddict = dict()
    sorted_workday = sorted(workday, key=lambda k: k['WORKERUSERID'])
    for r in sorted_workday:
        user = dict()
        userid = r["WORKERUSERID"].lower()
        if userid not in known['config']:
            LOGGER.info("%s is a new user", (userid))
        user['manager_userid'] = r['MANAGERUSERID'].lower()
        for key, val in translate.items():
            user[val] = r[key]
        ddict[userid] = user
        if quick and userid in known['config']:
            continue
        LOGGER.debug(user)
        if not rebuild:
            post_change(user, userid)
    LOGGER.info("Found %d active entries", len(ddict))
    if rebuild:
        LOGGER.info("workday config will contain %d Janelia entries", len(ddict))
        post_change(ddict)


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(
        description='Update Workday user Configuration')
    PARSER.add_argument('--quick', action='store_true', dest='QUICK',
                        default=False, help='Only process new entries')
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
    update_users(ARG.QUICK, ARG.REBUILD)
    print("Documents inserted in config database: %d" % count['insert'])
    print("Documents updated in config database: %d" % count['update'])

