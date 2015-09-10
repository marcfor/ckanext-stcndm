import sys
import json
import yaml
import ckanapi


def listify(value):
    if isinstance(value, unicode):
        return filter(None, map(unicode.strip, value.split(';')))  # filter removes empty strings
    elif isinstance(value, list):
        return filter(None, map(unicode.strip, value[0].split(';')))
    else:
        return []


def code_lookup(old_field_name, data_set, choice_list):
    _temp = data_set[old_field_name]
    field_values = listify(_temp)
    codes = []
    for field_value in field_values:
        code = None
        if '|' in field_value:
            (field_value, bogon) = field_value.split('|', 1)
        if old_field_name == 'archived_bi_strs' and field_value == 'Archive':
            field_value = 'Archived'
        for choice in choice_list:
            if choice['label']['en'].lower().strip() == field_value.lower().strip():
                if choice['value']:
                    code = choice['value']
        if not code:
            sys.stderr.write((u'publication-{0}: weird {1} .{2}.{3}.\n'.format(
                line['productidnew_bi_strs'],
                old_field_name,
                _temp,
                field_value)).encode('utf-8'))
        else:
            codes.append(code)
    return codes


def format_and_release(line):
    # format fields
    format_out = {
        u'owner_org': u'statcan',
        u'private': False,
        u'type': u'format',
        u'parent_slug': 'publication-{0}'.format(line['productidnew_bi_strs'].lower()),
        u'name':  (u'format-{0}_{1}'.format(line['productidnew_bi_strs'], line['formatcode_bi_txtm'])).lower(),
        u'title': (u'format-{0}_{1}'.format(line['productidnew_bi_strs'], line['formatcode_bi_txtm'])).lower()
    }

    if 'formatcode_bi_txtm' in line and line['formatcode_bi_txtm']:
        format_out['format_code'] = line['formatcode_bi_txtm']
    else:
        sys.stderr.write((u'{0} missing format\n').format(line['name']))

    temp = {}
    if 'issnnum_en_strs' in line and line['issnnum_en_strs']:
        temp[u'en'] = line['issnnum_en_strs']
    if 'issnnum_fr_strs' in line and line['issnnum_fr_strs']:
        temp[u'fr'] = line['issnnum_fr_strs']
    if temp:
        format_out['issn_number'] = temp

    temp = {}
    if 'url_en_strs' in line and line['url_en_strs']:
        temp[u'en'] = line['url_en_strs']
    if 'url_fr_strs' in line and line['url_fr_strs']:
        temp[u'fr'] = line['url_fr_strs']
    if temp:
        format_out['url'] = temp

    print json.dumps(format_out)

    # release fields

    release_out = {
        u'owner_org': u'statcan',
        u'private': False,
        u'type': u'release',
        u'parent_slug': format_out['name'],
        u'is_correction': '0'
    }

    temp = {}
    if 'adminnotes_bi_txts' in line and line['adminnotes_bi_txts']:
        temp[u'en'] = line['adminnotes_bi_txts']
        temp[u'fr'] = line['adminnotes_bi_txts']
    if temp:
        release_out['admin_notes'] = temp

    if 'releasedate_bi_strs' in line and line['releasedate_bi_strs']:
        release_out['release_date'] = line['releasedate_bi_strs']

    temp = {}
    if 'refperiod_en_txtm' in line:
        result = listify(line['refperiod_en_txtm'])
        if result:
            temp[u'en'] = result
    if 'refperiod_fr_txtm' in line:
        result = listify(line['refperiod_fr_txtm'])
        if result:
            temp[u'fr'] = result
    if temp:
        release_out['reference_periods'] = temp

    if 'lastpublishstatuscode_bi_strs' in line and line['lastpublishstatuscode_bi_strs']:
        release_out['publish_status_code'] = line['lastpublishstatuscode_bi_strs']

    if 'display_en_txtm' in line:
        result = code_lookup('display_en_txtm', line, display_list)
        if result:
            release_out['display_code'] = result

    if 'dispandtrack_bi_txtm' in line:
        result = code_lookup('dispandtrack_bi_txtm', line, tracking_list)
        if result:
            release_out['tracking_codes'] = result

    # release_out['name'] = u'release-{0}_{1}_{2}'.format(
    #     line['productidnew_bi_strs'],
    #     line['formatcode_bi_txtm'],
    #     release_out['release_id'])

    # release_out['title'] = u'release-{0}_{1}_{2}'.format(
    #     line['productidnew_bi_strs'],
    #     line['formatcode_bi_txtm'],
    #     release_out['release_id'])

    print json.dumps(release_out)


rc = ckanapi.RemoteCKAN('http://127.0.0.1:5000')

geolevel_list = []
status_list = []
tracking_list = []
archive_status_list = []
display_list = []
publish_list = []

results = rc.action.package_search(
    q='type:codeset',
    rows=1000)
for codeset in results['results']:
    if codeset['codeset_type'] == 'geolevel':
        geolevel_list.append({
            'label': codeset['title'],
            'value': codeset['codeset_value']
        })
#    if codeset['codeset_type'] == 'status':
#        status_list.append({
#            'label': codeset['title'],
#            'value': codeset['codeset_value']
#        })

subject_dict = {}

i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='type:subject',
        rows=1000,
        start=i*1000)
    n = query_results['count'] / 1000.0
    i += 1
    for result in query_results['results']:
        subject_dict[result['subject_code']] = result['title']

# geodescriptor_list = []
# results = rc.action.package_search(
#     q='type:geodescriptor',
#     rows=1000)
# for result in results['results']:
#     if 'geodescriptor_code' in result:
#         continue
#     geodescriptor_list.append({
#         'label': result['title'],
#         'value': result['geodescriptor_code']
#     })

dimension_member_list = []
results = rc.action.package_search(
    q='type:dimension_member',
    rows=1000)
for result in results['results']:
    if 'dimension_member_code' not in result:
        continue
    dimension_member_list.append({
        'label': result['title'],
        'value': result['dimension_member_code']
    })

# survey_source_list = []
# results = rc.action.package_search(
#     q='type:survey',
#     rows=1000)
# for result in results['results']:
#     survey_source_list.append({
#         'label': result['title'],
#         'value': result['product_id_new']
#     })

f = open('../schemas/presets.yaml')
presetMap = yaml.safe_load(f)
f.close()
for preset in presetMap['presets']:
    if preset['preset_name'] == 'ndm_archive_status':
        archive_status_list = preset['values']['choices']
        if not archive_status_list:
            raise ValueError('could not find archive status preset')
    if preset['preset_name'] == 'ndm_collection_methods':
        collection_method_list = preset['values']['choices']
        if not collection_method_list:
            raise ValueError('could not find collection method preset')
    if preset['preset_name'] == 'ndm_survey_status':
        survey_status_list = preset['values']['choices']
        if not survey_status_list:
            raise ValueError('could not find survey status preset')
    if preset['preset_name'] == 'ndm_survey_participation':
        survey_participation_list = preset['values']['choices']
        if not survey_participation_list:
            raise ValueError('could not find survey participation preset')
    if preset['preset_name'] == 'ndm_survey_owner':
        survey_owner_list = preset['values']['choices']
        if not survey_owner_list:
            raise ValueError('could not find survey owner preset')
    # if preset['preset_name'] == 'ndm_format':
    #     format_list = preset['values']['choices']
    #     if not format_list:
    #         raise ValueError('could not find format preset')
    if preset['preset_name'] == 'ndm_tracking':
        tracking_list = preset['values']['choices']
        if not tracking_list:
            raise ValueError('could not find tracking preset')
    if preset['preset_name'] == 'ndm_display':
        display_list = preset['values']['choices']
        if not display_list:
            raise ValueError('could not find display preset')
    if preset['preset_name'] == 'ndm_publish_status':
        publish_list = preset['values']['choices']
        if not publish_list:
            raise ValueError('could not find display preset')
    if preset['preset_name'] == 'ndm_status':
        status_list = preset['values']['choices']
        if not status_list:
            raise ValueError('could not find status preset')

rc = ckanapi.RemoteCKAN('http://ndmckanq1.stcpaz.statcan.gc.ca/zj')
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='pkuniqueidcode_bi_strs:public* AND title_en_txts:*',
        rows=1000,
        start=i*1000)
    n = query_results['count'] / 1000.0
    i += 1

    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        product_out = {
            u'owner_org': u'statcan',
            u'private': False,
            u'type': u'publication',
            u'product_type_code': u'20'}

        temp = {}
        if 'title_en_txts' in line and line['title_en_txts']:
            temp[u'en'] = line['title_en_txts']
        if 'title_fr_txts' in line and line['title_fr_txts']:
            temp[u'fr'] = line['title_fr_txts']
        if temp:
            product_out['title'] = temp

        temp = {}
        if 'description_en_txts' in line and line['description_en_txts']:
            temp[u'en'] = line['description_en_txts']
        if 'description_fr_txts' in line and line['description_fr_txts']:
            temp[u'fr'] = line['description_fr_txts']
        if temp:
            product_out['notes'] = temp

        if 'conttypecode_bi_txtm' in line:
            result = listify(line['conttypecode_bi_txtm'])
            if result:
                product_out['content_type_codes'] = result

        if 'geolevel_en_txtm' in line:
            result = code_lookup('geolevel_en_txtm', line, geolevel_list)
            if result:
                product_out['geolevel_codes'] = result

        if 'specificgeocode_bi_txtm' in line and line['specificgeocode_bi_txtm']:
            result = listify('specificgeocode_bi_txtm')
            if result:
                product_out['geodescriptor_codes'] = result

        if 'subjnewcode_bi_txtm' in line and line['subjnewcode_bi_txtm']:
            result = listify(line['subjnewcode_bi_txtm'])
            for subject_code in result:
                if subject_code not in subject_dict:
                    sys.stderr.write((u'{0}: unknown subject code: .{1}.\n'.format(
                        line['name'],
                        subject_code)).encode('utf-8'))
            product_out['subject_codes'] = result

        if 'subjoldcode_bi_txtm' in line and line['subjoldcode_bi_txtm']:
            result = listify(line['subjnewcode_bi_txtm'])
            product_out['subjectold_codes'] = result

        if 'related_bi_strm' in line and line['related_bi_strm']:
            result = listify(line['related_bi_strm'])
            if result:
                product_out['related_products'] = result

        temp = {}
        if 'stcthesaurus_en_txtm' in line:
            result = listify(line['stcthesaurus_en_txtm'])
            if result:
                temp[u'en'] = result
        if 'stcthesaurus_fr_txtm' in line:
            result = listify(line['stcthesaurus_fr_txtm'])
            if result:
                temp[u'fr'] = result
        if temp:
            product_out['thesaurus'] = temp

        if 'archivedate_bi_txts' in line and line['archivedate_bi_txts']:
            product_out['archive_date'] = line['archivedate_bi_txts']

        if 'archived_bi_strs' in line:
            result = code_lookup('archived_bi_strs', line, archive_status_list)
            if result:
                product_out['archive_status_code'] = result[0]

        # if 'defaultviewid_bi_strs' and line['defaultviewid_bi_strs']:
        #     product_out['default_view_id'] = line['defaultviewid_bi_strs']

        temp = {}
        if 'dimmembers_en_txtm':
            result = listify(line['dimmembers_en_txtm'])
            if result:
                temp[u'en'] = result
        if 'dimmembers_fr_txtm':
            result = listify(line['dimmembers_fr_txtm'])
            if result:
                temp[u'fr'] = result
        if temp:
            product_out['dimension_members'] = temp

        if 'frccode_bi_strs' in line and line['frccode_bi_strs']:
            product_out['frc'] = line['frccode_bi_strs']

        if 'arrayterminatedcode_bi_strs' in line and line['arrayterminatedcode_bi_strs']:
            product_out['array_terminated'] = line['arrayterminatedcode_bi_strs']

        if 'featureweight_bi_ints' in line and line['featureweight_bi_ints']:
            product_out['feature_weight'] = int(line['featureweight_bi_ints'])

        if 'freqcode_bi_txtm' in line and line['freqcode_bi_txtm']:
            result = listify('freqcode_bi_txtm')
            if result:
                product_out['frequency_codes'] = result

        if 'hierarchyid_bi_strm' in line and line['hierarchyid_bi_strm']:
            product_out['parent_product'] = line['hierarchyid_bi_strm']

        if 'extauthor_bi_txtm' in line and line['extauthor_bi_txtm']:
            result = listify(line['extauthor_bi_txtm'])
            if result:
                product_out['external_authors'] = result

        if 'intauthor_bi_txtm' in line and line['intauthor_bi_txtm']:
            result = listify(line['intauthor_bi_txtm'])
            if result:
                product_out['internal_authors'] = result

        temp = {}
        if 'histnotes_en_txts' in line and line['histnotes_en_txts']:
            temp[u'en'] = line['histnotes_en_txts']
        if 'histnotes_fr_txts' in line and line['histnotes_fr_txts']:
            temp[u'fr'] = line['histnotes_fr_txts']
        if temp:
            product_out['history_notes'] = temp

        temp = {}
        if 'doinum_en_strs' in line and line['doinum_en_strs']:
            temp[u'en'] = line['doinum_en_strs']
        if 'doinum_fr_strs' in line and line['doinum_fr_strs']:
            temp[u'fr'] = line['doinum_fr_strs']
        if temp:
            product_out['digital_object_identifier'] = temp

        if 'interncontactname_bi_txts' in line and line['interncontactname_bi_txts']:
            result = listify(line['interncontactname_bi_txts'])
            if result:
                product_out['internal_contacts'] = result

        temp = {}
        if 'keywordsuncon_en_txtm' in line:
            result = listify(line['keywordsuncon_en_txtm'])
            if result:
                temp[u'en'] = result
        if 'keywordsuncon_fr_txtm':
            result = listify(line['keywordsuncon_fr_txtm'])
            if result:
                temp[u'fr'] = result
        if temp:
            product_out['keywords'] = temp

        if 'productidnew_bi_strs' in line and line['productidnew_bi_strs']:
            product_out['product_id_new'] = line['productidnew_bi_strs']
            product_out['name'] = 'publication-{0}'.format(line['productidnew_bi_strs'].lower())

        if 'productidold_bi_strs' in line and line['productidold_bi_strs']:
            product_out['product_id_old'] = line['productidold_bi_strs']

        if 'pubyear_bi_intm' in line and line['pubyear_bi_intm']:
            product_out['publication_year'] = line['pubyear_bi_intm']

        if 'replaces_bi_strm' in line:
            result = listify(line['replaces_bi_strm'])
            if result:
                product_out['replaced_products'] = result

        if 'sourcecode_bi_txtm' in line and line['sourcecode_bi_txtm']:
            result = listify(line['sourcecode_bi_txtm'])
            if result:
                product_out['survey_source_codes'] = result

        if 'statusfcode_bi_strs' in line and line['statusfcode_bi_strs']:
            result = listify('statusfcode_bi_strs')
            if result:
                product_out['status_codes'] = result

        if 'license_title' in line:
            product_out['license_title'] = line['license_title']

        if 'license_url' in line:
            product_out['license_url'] = line['license_url']

        if 'license_id' in line:
            product_out['license_id'] = line['license_id']

        print json.dumps(product_out)

        format_and_release(line)

i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='pkuniqueidcode_bi_strs:public* AND -title_en_txts:*',
        rows=1000,
        start=i*1000)
    n = query_results['count'] / 1000.0
    i += 1

    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        format_and_release(line)
