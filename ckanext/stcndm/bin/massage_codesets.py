__author__ = 'marc'

import sys
import json
import ckanapi

lookup = {
    'extras_conttype_en_txtm': u'content_type',
    'extras_freq_en_txtm': u'frequency',
    # 'extras_statusf_en_strs': u'status',
    # geolevel is still a codeset but is treated separately
    # 'extras_geolevel_en_txtm': 'geolevel',
    # the following fields have become presets
    # 'extras_archived_bi_strs': 'archived',
    # 'extras_dispandtrack_bi_txtm': 'tracking',
    # 'extras_display_bi_txtm': 'display',
    # 'extras_format_en_txtm': 'format',
    # 'extras_producttype_en_strs': 'product_type',
    # 'extras_tmregorg_bi_tmtxtm': 'bogon',
    # 'extras_tmtaxdisp_en_tmtxtm': 'subject_display'
}

rc = ckanapi.RemoteCKAN('http://ndmckanq1.stcpaz.statcan.gc.ca/zj/')
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='organization:tmshortlist',
        rows=1000,
        start=i*1000)
    i += 1
    n = query_results['count'] / 1000.0
    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        old_content_type = line.get('tmdroplfld_bi_tmtxtm')
        if old_content_type in (
                'extras_archived_bi_strs',
                'extras_tmtaxdisp_en_tmtxtm',
                'extras_tmregorg_bi_tmtxtm',
                'extras_dispandtrack_bi_txtm',
                'extras_producttype_en_strs',
                'extras_geolevel_en_txtm',
                'extras_format_en_txtm',
                'extras_statusf_en_strs',
                'extras_display_bi_txtm'
        ):
            continue  # skip the tmshorlist that are handled separately

        data = line.get(u'tmdroplopt_bi_tmtxtm', u'')
        english_value, french_value, code_value, bogon = map(unicode.strip, (data + u'|||').split(u'|', 3))
        if not code_value:
            sys.stderr.write('missing code value for {0} {1}\n'.format(old_content_type, data))
            continue
        else:
            codeset_type = lookup.get(line.get('tmdroplfld_bi_tmtxtm'))
            line_out = {
                u'owner_org': u'statcan',
                u'private': False,
                u'type': u'codeset',
                u'name': u'{0}-{1}'.format(codeset_type, code_value),
                u'codeset_type': lookup[old_content_type],
                u'codeset_value': code_value,
                u'title_translated': {
                    u'en': english_value,
                    u'fr': french_value
                },
                u'license_title': line.get(u'license_title', u''),
                u'license_url': line.get(u'license_url', u''),
                u'license_id': line.get(u'license_id', u'')
            }

        print json.dumps(line_out)
