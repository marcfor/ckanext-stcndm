import json
import ckanapi
import ConfigParser

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
        q='organization:ndprovsgc',
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
            u'type': u'province',
            u'geolevel': line.get('tmprovgeolevel_bi_tmtxtm', ''),
            u'title_translated': {
                u'en': line.get('tmprovgeoname_en_tmtxtm', ''),
                u'fr': line.get('tmprovgeoname_fr_tmtxtm', '')
            },
            u'geotype': line.get('tmprovgeotype_bi_tmtxtm', ''),
            u'sgc_code': line.get('tmprovsgccode_bi_tmtxtm', ''),
            u'name': u'province-{sgc_code}'.format(
                sgc_code=line.get('tmprovsgccode_bi_tmtxtm', '')
            ),
            u'sort_order': line.get('tmprovsortorder_bi_tmints', ''),

            u'license_title': line.get('license_title', ''),
            u'license_url': line.get('license_url', ''),
            u'license_id': line.get('license_id', ''),
        }

        print json.dumps(line_out)
