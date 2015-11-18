import json
import ckanapi
import ConfigParser
import re

__author__ = 'marc'

parser = ConfigParser.SafeConfigParser()
parser.read("./ckanparameters.config")

API_KEY = parser.get("ckanqa", "api_key")
BASE_URL = parser.get("ckanqa", "base_url")


def listify(value):
    if isinstance(value, unicode):
        return filter(None, map(unicode.strip, value.split(';')))  # filter removes empty strings
    elif isinstance(value, list):
        return filter(None, map(unicode.strip, value[0].split(';')))
    else:
        return []

rc = ckanapi.RemoteCKAN(BASE_URL)  # 'http://ndmckanq1.stcpaz.statcan.gc.ca/zj/'
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='organization:tmsgccode',
        rows=1000,
        start=i*1000)
    i += 1
    n = query_results['count'] / 1000.0
    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        line_out = {
            u'owner_org': u'statcan',
            u'private': False,
            u'type': u'geodescriptor',
            u'product_id_old': line.get('10uid_bi_strs', ''),
            u'title_translated': {
                u'en': line.get(u'tmsgcname_en_tmtxtm', ''),
                u'fr': line.get(u'tmsgcname_fr_tmtxtm', ''),
            },
            u'geolevel_codes': line.get(u'tmsgccode_bi_tmtxtm', ''),
            u'license_title': line.get(u'license_title', ''),
            u'license_url': line.get(u'license_url', ''),
            u'license_id': line.get(u'license_id', ''),
        }
        geodescriptor_code = line.get(u'tmsgcspecificcode_bi_tmtxtm', '')
        if ';' in geodescriptor_code:
            line_out[u'aliased_codes'] = listify(geodescriptor_code)
            line_out[u'geodescriptor_code'] = line_out[u'geolevel_codes']
            line_out[u'name'] = u'geodescriptor-{geolevel_code}'.format(
                geolevel_code=line_out[u'geolevel_codes'].lower()
            )
        else:
            line_out[u'geodescriptor_code'] = line.get(u'tmsgcspecificcode_bi_tmtxtm', '')
            line_out[u'name'] = u'geodescriptor-{geodescriptor_code}'.format(
                geodescriptor_code=geodescriptor_code.lower()
            )
        line_out[u'name'] = re.sub(r"[^a-zA-Z0-9\-_]", "_", line_out[u'name'])
        print json.dumps(line_out)
