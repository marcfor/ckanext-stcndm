import sys, os, inspect
import yaml
import ckanapi
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import gettz
import re

__author__ = 'marc'

format_lookup = {
    'audio': '1',
    'database': '2',
    'cd-rom': '3',
    'diskette': '4',
    'fax/email': '5',
    'other': '7',
    'pdf': '8',
    'kit': '9',
    'microfiche': '10',
    'paper': '12',
    'symposium/workshop': '13',
    'tape/cassette': '14',
    'dvd': '15',
    'print pdf': '16',
    'html': '17',
    'video': '18',
    'etf': '19'
}

default_date = datetime(1, 1, 1, 0, 0, 0, 0, tzinfo=gettz('America/Toronto'))
default_release_date = datetime(1, 1, 1, 8, 30, 0, 0,
                                tzinfo=gettz('America/Toronto'))


def to_utc(date_str, def_date=default_date):
    result = parse(date_str, default=def_date)
    utc_result = result.astimezone(gettz('UTC'))
    return utc_result.replace(tzinfo=None).isoformat()


def in_and_def(key, a_dict):
    if key in a_dict and a_dict[key]:
        return True
    else:
        return False


def listify(value):
    if isinstance(value, unicode):
        return filter(None, map(unicode.strip, value.split(';')))
        # filter removes empty strings
    elif isinstance(value, list):
        return filter(None, map(unicode.strip, value[0].split(';')))
    else:
        return []


def code_lookup(old_field_name, data_set, choice_list):
    temp = data_set[old_field_name]
    field_values = listify(temp)
    codes = []
    for field_value in field_values:
        code = None
        if '|' in field_value:
            (field_value, bogon) = field_value.split('|', 1)
        elif '/' in field_value:
            (field_value, bogon) = field_value.split('/', 1)
        for choice in choice_list:
            if choice[u'label'][u'en'].lower().strip() == \
                    field_value.lower().strip():
                if choice[u'value']:
                    code = choice[u'value']
        if not code:
            sys.stderr.write('{product_id}: unrecognized {old_name}: '
                             '{field_value}.\n'.format(
                                product_id=data_set[u'productidnew_bi_strs'],
                                old_name=old_field_name,
                                field_value=field_value))
        else:
            codes.append(code)
    return codes


def do_product(data_set):
    deleted_subject_codes = [
        '130901',
        '140206',
        '2101',
        '26',
        '2602',
        '2603',
        '2606',
        '2699',
        '3103',
        '3404',
        '3451',
        '3452',
        '350301',
        '3507',
        '3706',
        '3710',
        '380401',
        '4302',
        '4304',
        '4307',
        '673901',
        '675178'
    ]
    product_out = {
        u'owner_org': u'statcan',
        u'private': False,
        u'admin_notes': {
            u'en': data_set.get(u'adminnotes_bi_txts', ''),
            u'fr': data_set.get(u'adminnotes_bi_txts', '')
        },
        u'array_terminated_code':
            data_set.get(u'arrayterminatedcode_bi_strs', ''),
        u'coordinates': data_set.get(u'coordinates_bi_instrs', ''),
        u'default_view_id': data_set.get(u'defaultviewid_bi_strs', ''),
        u'notes': {
          u'en': data_set.get(u'description_en_txts', data_set.get(
              u'description_en_intxts', u'')),
          u'fr': data_set.get(u'description_fr_txts', data_set.get(
              u'description_fr_intxts', u''))
        },
        u'display_order': data_set.get(u'displayorder_bi_inints', ''),
        u'digital_object_identifier': {
            u'en': data_set.get(u'doinum_en_strs', ''),
            u'fr': data_set.get(u'doinum_fr_strs', '')
        },
        u'feature_weight': data_set.get(
            u'featureweight_bi_ints', data_set.get(
                u'featureweight_bi_inints', u'')
            ),
        u'frc': data_set.get(u'frccode_bi_strs', ''),
        u'history_notes': {
            u'en': data_set.get(u'histnotes_en_txts', ''),
            u'fr': data_set.get(u'histnotes_fr_txts', '')
        },
        u'last_publish_status_code':
            data_set.get(u'lastpublishstatuscode_bi_strs', ''),
        u'license_id': data_set.get(u'license_id', ''),
        u'license_title': data_set.get(u'license_title', ''),
        u'license_url': data_set.get(u'license_url', ''),
        u'pe_code': data_set.get(u'pecode_bi_strs', ''),
        u'price': data_set.get(u'price_bi_txts', ''),
        u'price_notes': {
            u'en': data_set.get(u'pricenote_en_txts', ''),
            u'fr': data_set.get(u'pricenote_fr_txts', '')
        },
        u'product_id_new': data_set.get(u'productidnew_bi_strs', '').upper(),
        u'product_id_old': data_set.get(u'productidold_bi_strs', ''),
        u'product_type_code': data_set.get(u'producttypecode_bi_strs', ''),
        u'publication_year': data_set.get(u'pubyear_bi_intm', ''),
        u'reference_period': {
            u'en': data_set.get(u'refperiod_en_txtm', u''),
            u'fr': data_set.get(u'refperiod_fr_txtm', u''),
        },
        u'title': {
            u'en': data_set.get(u'title_en_txts', ''),
            u'fr': data_set.get(u'title_fr_txts', '')
        },
        u'volume_and_number': data_set.get(u'volumeandnum_bi_txts', ''),

    }

    if in_and_def(u'archivedate_bi_txts', data_set):
        product_out[u'archive_date'] = to_utc(
            data_set.get(u'archivedate_bi_txts'),
            default_date)

    if in_and_def(u'archived_bi_strs', data_set):
        result = code_lookup(u'archived_bi_strs', data_set, archive_status_list)
        if result:
            product_out[u'archive_status_code'] = result[0]

    if in_and_def(u'calculation_bi_instrm', data_set):
        result = listify(data_set[u'calculation_bi_instrm'])
        if result:
            product_out[u'calculations'] = result

    if in_and_def(u'conttypecode_bi_txtm', data_set):
        result = listify(data_set[u'conttypecode_bi_txtm'])
        if result:
            product_out[u'content_type_codes'] = result

    temp = {}
    if in_and_def(u'dimmembers_en_txtm', data_set):
        result = listify(data_set[u'dimmembers_en_txtm'])
        if result:
            temp[u'en'] = result
    if in_and_def(u'dimmembers_fr_txtm', data_set):
        result = listify(data_set[u'dimmembers_fr_txtm'])
        if result:
            temp[u'fr'] = result
    if temp:
        product_out[u'dimension_members'] = temp

    if in_and_def(u'display_bi_txtm', data_set):
        result = code_lookup(u'display_bi_txtm', data_set, display_list)
        if result:
            product_out[u'display_code'] = result[0]

    if in_and_def(u'dispandtrack_bi_txtm', data_set):
        result = code_lookup(u'dispandtrack_bi_txtm', data_set, tracking_list)
        if result:
            product_out[u'tracking_codes'] = result

    if in_and_def(u'extauthor_bi_txtm', data_set):
        result = listify(data_set[u'extauthor_bi_txtm'])
        if result:
            product_out[u'external_authors'] = result

    if in_and_def(u'freqcode_bi_txtm', data_set):
        result = listify(data_set[u'freqcode_bi_txtm'])
        if result:
            product_out[u'frequency_codes'] = result

    if in_and_def(u'freqcode_bi_intxtm', data_set):
        result = listify(data_set[u'freqcode_bi_intxtm'])
        if result:
            product_out[u'frequency_codes'] = result

    if in_and_def(u'geolevel_en_txtm', data_set):
        result = code_lookup(u'geolevel_en_txtm', data_set, geolevel_list)
        if result:
            product_out[u'geolevel_codes'] = result

    if in_and_def(u'geonamecode_bi_intxtm', data_set):
        result = listify(data_set[u'geonamecode_bi_intxtm'])
        if result:
            product_out[u'geodescriptor_codes'] = result

    if in_and_def(u'hierarchyid_bi_strm', data_set):
        result = listify(data_set[u'hierarchyid_bi_strm'])
        if result:
            product_out[u'top_parent_id'] = result[0].upper()

    if in_and_def(u'hierarchyid_bi_strs', data_set):
        result = listify(data_set[u'hierarchyid_bi_strs'])
        if result:
            product_out[u'top_parent_id'] = result[0].upper()

    if in_and_def(u'intauthor_bi_txtm', data_set):
        result = listify(data_set[u'intauthor_bi_txtm'])
        if result:
            product_out[u'internal_authors'] = result

    if in_and_def(u'interncontactname_bi_txts', data_set):
        result = listify(data_set[u'interncontactname_bi_txts'])
        if result:
            product_out[u'internal_contacts'] = result

    if in_and_def(u'issueno_bi_strs', data_set):
        if re.match('\d{7}', data_set[u'issueno_bi_strs']):
            product_out[u'issue_number'] = data_set.get(u'issueno_bi_strs')
        else:
            sys.stderr.write('{product_id}: unrecognized issue_number: '
                             '{issue_number}.\n'.format(
                                product_id=data_set[u'productidnew_bi_strs'],
                                issue_number=data_set[u'issueno_bi_strs']))

    temp = {}
    if in_and_def(u'keywordsuncon_en_txtm', data_set):
        result = listify(data_set[u'keywordsuncon_en_txtm'])
        if result:
            temp[u'en'] = result
    if in_and_def(u'keywordsuncon_fr_txtm', data_set):
        result = listify(data_set[u'keywordsuncon_fr_txtm'])
        if result:
            temp[u'fr'] = result
    if temp:
        product_out[u'keywords'] = temp

    if in_and_def(u'releasedate_bi_strs', data_set):
        product_out[u'last_release_date'] = to_utc(
            data_set.get(u'releasedate_bi_strs'),
            default_release_date)

    if in_and_def(u'legacydate_bi_txts', data_set):
        product_out[u'legacy_date'] = to_utc(
            data_set.get(u'legacydate_bi_txts'),
            default_date)

    if in_and_def(u'ndmstate_en_intxtm', data_set):
        result = listify(data_set[u'ndmstate_en_intxtm'])
        if result:
            product_out[u'ndm_states'] = result

    if in_and_def(u'related_bi_strm', data_set):
        result = listify(data_set[u'related_bi_strm'])
        if result:
            product_out[u'related_products'] = result

    temp = {}
    if in_and_def(u'relatedcontent_en_txtm', data_set):
        result = listify(data_set[u'relatedcontent_en_txtm'])
        if result:
            temp[u'en'] = result
    if in_and_def(u'relatedcontent_fr_txtm', data_set):
        result = listify(data_set[u'relatedcontent_fr_txtm'])
        if result:
            temp[u'fr'] = result
    if temp:
        product_out[u'related_content'] = temp

    if in_and_def(u'replaces_bi_txtm', data_set):
        result = listify(data_set[u'replaces_bi_txtm'])
        if result:
            product_out[u'replaced_products'] = result

    if in_and_def(u'sourcecode_bi_txtm', data_set):
        result = listify(data_set[u'sourcecode_bi_txtm'])
        if result:
            product_out[u'survey_source_codes'] = result

    if in_and_def(u'specificgeocode_bi_txtm', data_set):
        result = listify(data_set[u'specificgeocode_bi_txtm'])
        if result:
            product_out[u'geodescriptor_codes'] = result

    if in_and_def(u'statusfcode_bi_strs', data_set):
        if data_set[u'statusfcode_bi_strs'] == '33':
            # tease out discontinued to a new field
            product_out[u'discontinued_code'] = '1'
        elif data_set[u'statusfcode_bi_strs'] == '36':
            # tease out do not load to OLC to a new field
            product_out[u'load_to_olc_code'] = '0'
        else:
            product_out[u'status_code'] = data_set[u'statusfcode_bi_strs']

    temp = {}
    if in_and_def(u'stcthesaurus_en_txtm', data_set):
        result = listify(data_set[u'stcthesaurus_en_txtm'])
        if result:
            temp[u'en'] = result
    if in_and_def(u'stcthesaurus_fr_txtm', data_set):
        result = listify(data_set[u'stcthesaurus_fr_txtm'])
        if result:
            temp[u'fr'] = result
    if temp:
        product_out[u'thesaurus_terms'] = temp

    if in_and_def(u'subjnewcode_bi_txtm', data_set):
        result = listify(data_set[u'subjnewcode_bi_txtm'])
        if result:
            for code in deleted_subject_codes:
                if code in result:
                    result.remove(code)
            product_out[u'subject_codes'] = list(set(result))

    if in_and_def(u'subjoldcode_bi_txtm', data_set):
        result = listify(data_set[u'subjoldcode_bi_txtm'])
        if result:
            product_out[u'subjectold_codes'] = result

    if in_and_def(u'tableid_bi_instrm', data_set):
        result = listify(data_set[u'tableid_bi_instrm'])
        if result:
            product_out[u'table_ids'] = result

    return product_out


def do_format(data_set):
    format_code = data_set.get('formatcode_bi_txtm')
    if not format_code:
        format_code = format_lookup.get(data_set.get('format_en_txtm').lower())
    if format_code not in format_lookup.values():
        return {}

    format_out = {
        u'owner_org': u'statcan',
        u'private': False,
        u'type': u'format',
        u'name': u'format-{product_id}_{format_code}'.format(
            product_id=data_set.get(
                u'productidnew_bi_strs',
                u'product_id'),
            format_code=format_code.zfill(2)
        ).lower(),
        u'parent_id': data_set.get(
            u'productidnew_bi_strs',
            u'product_id').upper(),
        u'format_code': format_code,
        u'format_id': u'{product_id}_{format_code}'.format(
            product_id=data_set.get(u'productidnew_bi_strs', u'product_id'),
            format_code=format_code.zfill(2)
        ).lower(),
        u'isbn_number': {
            u'en': data_set.get(u'isbnnum_en_strs', u''),
            u'fr': data_set.get(u'isbnnum_fr_strs', u'')
            },
        u'issn_number': {
            u'en': data_set.get(u'issnnum_en_strs', u''),
            u'fr': data_set.get(u'issnnum_fr_strs', u'')
        },
        u'url': {
            u'en': data_set.get(
                u'url_en_strs', data_set.get(
                    u'url_en_instrs', u'')
                ),
            u'fr': data_set.get(
                u'url_fr_strs', data_set.get(
                    u'url_fr_instrs', u'')
                )
            },
        u'top_parent_id': data_set.get(
            u'hierarchyid_bi_strm', data_set.get(
                u'hierarchyid_bi_strs', data_set.get(
                    u'productidnew_bi_strs', u'').upper()
            )
        )
    }
    if in_and_def(u'releasedate_bi_strs', data_set):
        format_out[u'last_release_date'] = to_utc(
            data_set.get(u'releasedate_bi_strs'),
            default_release_date)

    return format_out

path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

f = open(path+'/../../schemas/presets.yaml')
presetMap = yaml.safe_load(f)
f.close()

archive_status_list = []
display_list = []
publish_list = []
status_list = []
tracking_list = []

for preset in presetMap[u'presets']:
    if preset[u'preset_name'] == 'ndm_archive_status':
        archive_status_list = preset[u'values'][u'choices']
        if not archive_status_list:
            raise ValueError('could not find archive status preset')
    if preset[u'preset_name'] == 'ndm_collection_methods':
        collection_method_list = preset[u'values'][u'choices']
        if not collection_method_list:
            raise ValueError('could not find collection method preset')
    if preset[u'preset_name'] == 'ndm_survey_status':
        survey_status_list = preset[u'values'][u'choices']
        if not survey_status_list:
            raise ValueError('could not find survey status preset')
    if preset[u'preset_name'] == 'ndm_survey_participation':
        survey_participation_list = preset[u'values'][u'choices']
        if not survey_participation_list:
            raise ValueError('could not find survey participation preset')
    if preset[u'preset_name'] == 'ndm_survey_owner':
        survey_owner_list = preset[u'values'][u'choices']
        if not survey_owner_list:
            raise ValueError('could not find survey owner preset')
    # if preset[u'preset_name'] == 'ndm_format':
    #     format_list = preset[u'values'][u'choices']
    #     if not format_list:
    #         raise ValueError('could not find format preset')
    if preset[u'preset_name'] == 'ndm_tracking':
        tracking_list = preset[u'values'][u'choices']
        if not tracking_list:
            raise ValueError('could not find tracking preset')
    if preset[u'preset_name'] == 'ndm_status':
        status_list = preset[u'values'][u'choices']
        if not status_list:
            raise ValueError('could not find ndm_status preset')
    if preset[u'preset_name'] == 'ndm_display':
        display_list = preset[u'values'][u'choices']
        if not display_list:
            raise ValueError('could not find display preset')
    if preset[u'preset_name'] == 'ndm_publish_status':
        publish_list = preset[u'values'][u'choices']
        if not publish_list:
            raise ValueError('could not find display preset')

geolevel_list = []
rc = ckanapi.RemoteCKAN('http://127.0.0.1:5000')
results = rc.action.package_search(
    q='type:codeset',
    rows=1000)
for codeset in results[u'results']:
    if codeset[u'codeset_type'] == 'geolevel':
        geolevel_list.append({
            'label': codeset[u'title'],
            'value': codeset[u'codeset_value']
        })
