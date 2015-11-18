__author__ = 'marc'

import json
import ckanapi


def listify(value):
    if isinstance(value, unicode):
        return filter(None, map(unicode.strip, value.split(';')))  # filter removes empty strings
    elif isinstance(value, list):
        return filter(None, map(unicode.strip, value[0].split(';')))
    else:
        return []


rc = ckanapi.RemoteCKAN('http://ndmckanq1.stcpaz.statcan.gc.ca/zj/')
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='organization:tmtaxonomy',
        rows=1000,
        start=i*1000)
    i += 1
    n = query_results['count'] / 1000.0
    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        line_out = {u'owner_org': u'statcan',
                    u'private': False,
                    u'type': u'subject'}

        if 'tmtaxdisp_en_tmtxtm' in line:
            if line['tmtaxdisp_en_tmtxtm'] == 'a_to_z':
                line_out['subject_display_code'] = '1'
            elif line['tmtaxdisp_en_tmtxtm'] == 'taxonomy':
                line_out['subject_display_code'] = '2'
            elif line['tmtaxdisp_en_tmtxtm'] == 'both':
                line_out['subject_display_code'] = '3'
            elif line['tmtaxdisp_en_tmtxtm'] == 'hide':
                line_out['subject_display_code'] = '4'

        temp = {}
        if 'tmtaxsubj_en_tmtxtm' in line and line['tmtaxsubj_en_tmtxtm']:
            temp[u'en'] = line['tmtaxsubj_en_tmtxtm']
        if 'tmtaxsubj_fr_tmtxtm' in line and line['tmtaxsubj_fr_tmtxtm']:
            temp[u'fr'] = line['tmtaxsubj_fr_tmtxtm']
        if temp:
            line_out['title_translated'] = temp

        temp = {}
        if 'tmtaxdescription_en_tmtxts' in line and line['tmtaxdescription_en_tmtxts']:
            temp[u'en'] = line['tmtaxdescription_en_tmtxts']
        if 'tmtaxdescription_fr_tmtxts' in line and line['tmtaxdescription_fr_tmtxts']:
            temp[u'fr'] = line['tmtaxdescription_fr_tmtxts']
        if temp:
            line_out['notes_translated'] = temp

        if 'tmtaxsubjcode_bi_tmtxtm' in line:
            line_out['subject_code'] = line['tmtaxsubjcode_bi_tmtxtm']
            line_out['name'] = 'subject-{0}'.format(line['tmtaxsubjcode_bi_tmtxtm'])

        if 'tmtaxadminnotes_bi_tmtxts' in line and line['tmtaxadminnotes_bi_tmtxts']:
            line_out['admin_notes'] = {
                u'en': line['tmtaxadminnotes_bi_tmtxts'],
                u'fr': line['tmtaxadminnotes_bi_tmtxts']
            }

        if 'tmtaxsubjoldcode_bi_tmtxtm' in line:
            line_out['subjectold_codes'] = map(unicode.strip, line['tmtaxsubjoldcode_bi_tmtxtm'].split(';'))

        temp = {}
        if 'tmtaxatozalias_en_tmtxtm' in line and line['tmtaxatozalias_en_tmtxtm']:
            temp[u'en'] = listify(line['tmtaxatozalias_en_tmtxtm'])
        if 'tmtaxatozalias_fr_tmtxtm' in line and line['tmtaxatozalias_fr_tmtxtm']:
            temp[u'fr'] = listify(line['tmtaxatozalias_fr_tmtxtm'])
        if temp:
            line_out['a_to_z_alias'] = temp

        if 'license_title' in line:
            line_out['license_title'] = line['license_title']

        if 'license_url' in line:
            line_out['license_url'] = line['license_url']

        if 'license_id' in line:
            line_out['license_id'] = line['license_id']

        print json.dumps(line_out)
