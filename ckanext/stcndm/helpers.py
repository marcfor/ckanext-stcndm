import ast
import ckanapi
from ckan.logic import _, ValidationError, get_action
import ckan.model as model
from ckan.common import c
import re
from ckanext.scheming.helpers import (
    scheming_get_preset,
    scheming_dataset_schemas
)

__author__ = 'matt'


class NotValidProduct(Exception):
    pass


def dict_list2dict(dict_list):
    d = dict()

    for dict_item in dict_list:
        d[dict_item['key']] = dict_item['value']

    return d


def x2list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return map(unicode.strip, unicode(value).split(';'))
    if isinstance(value, unicode):
        return map(unicode.strip, value.split(';'))
    if isinstance(value, dict):
        return dict2dict_list(value)
    return []


def dict2dict_list(dictionary):
    dl = list()

    for key in dictionary.keys():
        dl.append({'key': key, 'value': dictionary[key]})

    return dl


def get_schema(org, dataset):
    """
    Return a dict having fields in a given org for keys and the values stored
    for that field in the tmschema organization as a dict.

    :return: dict of dicts
    """

    context = {'model': model, 'session': model.Session, 'user': c.user}

    data_dict = {'org': org, 'dataset': dataset}

    result = get_action('ndm_get_schema')(context, data_dict)

    return result


def get_dataset_types():
    lc = ckanapi.LocalCKAN()
    types = lc.action.package_search(
        q='*:*',
        rows=0,
        facet='true',
        **{"facet.field": ["dataset_type"]}
    )['search_facets']['dataset_type']['items']
    schemas = scheming_dataset_schemas()
    result = {}

    for schema in schemas:
        result[schema] = {
            'title': schemas[schema]['catalog_type_label'],
            'count': 0
        }

        for type in types:
            if schema == type['name']:
                result[schema]['count'] = type['count']
                break

    return sorted(result.iteritems(), key=lambda type: type[1], reverse=True)


def get_parent_dataset(top_parent_id, dataset_id):
    lc = ckanapi.LocalCKAN()

    q = 'product_id_new:{parent_id}'.format(parent_id=top_parent_id)

    if dataset_id:
        q += 'AND NOT product_id_new:{id}'.format(id=dataset_id)

    parents = lc.action.package_search(
        q=q,
        sort='metadata_created ASC',
        rows=1000
    )['results']

    if parents:
        return parents[0]


def get_child_datasets(dataset_id):
    lc = ckanapi.LocalCKAN()
    return lc.action.package_search(
        q='top_parent_id:{pid} AND NOT product_id_new:{pid}'.format(
            pid=dataset_id
        ),
        rows=1000
    )['results']


def generate_revision_list(data_set):
    """
    :param data_set:
    :return:
    """
    # FIXME: Placeholder? What is this method for.
    # context = {'model': model, 'session': model.Session, 'user': c.user}


# TODO: rename this
def show_fields_changed_between_revisions(pkg_name, pkg_revisions):
    """
    :param pkg_name: name or id of package
    :type pkg_name: str
    :param pkg_revisions: revision details
    :type pkg_revisions: list of dicts

    :return: string
    """

    context = {'model': model, 'session': model.Session, 'user': c.user}

    revisions_dict = {}

    revision_order = []
    for revision in pkg_revisions:

        # The revision id needs to be passed through the context rather than
        # data_dict (base CKAN quirk)
        context['revision_id'] = revision['id']

        revision_pkg = get_action('package_show')(context, {'id': pkg_name})

        revision_extras_dict = {}

        # TODO: This will change when we move to scheming, but presently only
        # extras are important

        for extra in revision_pkg['extras']:
            revision_extras_dict[extra['key']] = extra['value']

        revisions_dict[revision['id']] = revision_extras_dict

        revision_order.append(revision['id'])

    def _pairs(lst):
        i = iter(lst)
        prev = i.next()
        for item in i:
            yield prev, item
            prev = item

    revisions_to_compare = _pairs(revision_order)

    next_record = {}
    modified_fields_dict = {}

    for pair in revisions_to_compare:

        new_dict = revisions_dict[pair[0]]
        old_dict = revisions_dict[pair[1]]

        modified_fields_dict[pair[0]] = []
        for k, v in new_dict.iteritems():

            try:
                if old_dict[k] != new_dict[k]:
                    modified_fields_dict[pair[0]].append(k)
            except KeyError:
                # also include added and deleted fields
                modified_fields_dict[pair[0]].append(k)

        modified_fields_dict[pair[0]].sort()

        next_record[pair[0]] = pair[1]

    return {
        'modified_fields': modified_fields_dict,
        'next_record': next_record
    }


class GeoLevel:
    def __init__(self, context):
        self.geo_table = {}

        self.get_geolevel_table(context)

    def get_geolevel_table(self, context):

        q = 'zckownerorg_bi_strs:tmshortlist'
        fq = 'tmdroplfld_bi_tmtxtm:extras_geolevel_en_txtm'

        data_dict = {'q': q, 'fq': fq, 'rows': '1000'}

        response = get_action('package_search')(context, data_dict)

        for result in response['results']:
            result_dict = {}

            for extra in result['extras']:
                result_dict[extra['key']] = extra['value']

            split_values = result_dict['tmdroplopt_bi_tmtxtm'].split('|')
            # ignore if no code is present (len < 3)
            if len(split_values) == 3:
                split_values = [value.strip() for value in split_values]
                (en_text, fr_text, code) = split_values
                self.geo_table[code] = (en_text, fr_text)

        return

    def get_by_code(self, code):

        return self.geo_table.get(code, (None, None))


class GeoSpecific:
    """
    The geo specific table (tmsgccode) is over 6k records so it shouldn't be
    loaded entirely like tmshortlist.
    Code descriptions will be searched when required.

    """
    def __init__(self, context):
        self.context = context

    def get_by_code(self, code):
        """
        :param code: code for specific geo code
        :type code: str

        :return: tuple of english and french descriptions
        """
        q = (
            'zckownerorg_bi_strs:tmsgccode AND '
            'tmsgcspecificcode_bi_tmtxtm:{code}'
        ).format(code=code)

        data_dict = {'q': q, 'rows': '1'}

        response = get_action('package_search')(self.context, data_dict)

        if response['count'] == 0:
            raise ValidationError((_('Specific Geo code not found.'),))

        # This is very messy but the tmsgccode entries might have multiple
        # codes as in the "all provinces" entry.  If this is the case, iterate
        # through them and eliminate entries that start with "all."
        if response['count'] > 1:
            result = None
            for res in response['results']:
                for extra in res['extras']:
                    if extra['key'] == 'tmsgccode_bi_tmtxtm':
                        if not extra['value'].lower().startswith('all'):
                            result = res
                        break
                if result:
                    break
        else:
            result = response['results'][0]

        if result:
            result_dict = {}

            for extra in result['extras']:
                result_dict[extra['key']] = extra['value']

            en_text = result_dict.get('tmsgcname_en_tmtxtm', '')
            fr_text = result_dict.get('tmsgcname_fr_tmtxtm', '')
        else:
            en_text = fr_text = None

        return en_text, fr_text


def codeset_choices(codeset_type):
    """
    Return a dictionary of {codeset_value: title} for the codeset_type
    passed

    :param codeset_type: codeset type for which to return values and labels
    :type codeset_type: str

    :return dict
    """
#    rc = ckanapi.RemoteCKAN('http://127.0.0.1:5000/')
    lc = ckanapi.LocalCKAN()
    results = lc.action.package_search(
        q='type:codeset',
        fq='codeset_type:' + codeset_type,
        rows=1000)
    return dict((r['codeset_value'], r.get('title_translated', r.get('title')))
                for r in results['results'])


def lookup_label(field_name, field_value, lookup_type):
    """
    Given the name of a field, the value of the field, and the type of lookup
    to perform, resolve the code and return the label.

    :param field_name: The name of the field being resolved (ex: format_code).
    :param field_value: The value of the field being resolved. (ex: '33')
    :param lookup_type: The type of field being resolved (ex: codeset)

    :return dict
    """
    lc = ckanapi.LocalCKAN()

    if not field_value:
        return {u'en': '', u'fr': ''}

    default = {
        u'en': 'label for ' + field_value,
        u'fr': 'description de ' + field_value,
        u'found': False
    }

    if not lookup_type:
        return default

    if lookup_type == 'preset':
        preset = scheming_get_preset('ndm_{f}'.format(f=field_name))
        if not preset:
            return default

        choices = preset['choices']
        for choice in choices:
            if choice['value'] == field_value:
                return choice['label']

        return default
    elif lookup_type == 'codeset':
        results = lc.action.package_search(
            q=(
                u'dataset_type:codeset AND '
                'codeset_type:{f} AND '
                'codeset_value:{v}'
            ).format(
                f=field_name,
                v=field_value
            )
        )

        if not results[u'count']:
            return default

        last_result = results[u'results'][-1]
        result = last_result.get(u'title_translated', last_result.get(u'title'))
        if isinstance(result, basestring):
            try:
                result = ast.literal_eval(result)
            except SyntaxError:
                pass

        return result
    else:
        results = lc.action.package_search(
            q=(
                u'dataset_type:{lookup_type} AND '
                'name:{lookup_type}-{field_value}'
            ).format(
                lookup_type=lookup_type,
                field_value=field_value.lower()
            )
        )
        if not results[u'count']:
            return default

        last_result = results[u'results'][-1]
        result = last_result.get(u'title_translated', last_result.get(u'title'))
        if isinstance(result, basestring):
            try:
                result = ast.literal_eval(result)
            except SyntaxError:
                pass

        return result


def next_correction_id():
    """
    :return next available correction id
    """
    lc = ckanapi.LocalCKAN()
    result = lc.action.package_search(
        q='correction_id:*',
        sort='correction_id DESC',
        rows=1
    )

    last_id = 0
    if result['count'] and 'correction_id' in result['results'][0]:
        try:
            last_id = int(result['results'][0]['correction_id'])
        except ValueError:
            pass
    if last_id >= 2000:
        return unicode(last_id + 1)
    else:
        return u'2000'


def next_non_data_product_id(subject_code, product_type_code):
    """
    Get next available product ID
    :param subject_code:
    :type subject_code: 2 digit str
    :param product_type_code:
    :type product_type_code: 2 digit str
    :return:
    """
    valid_product_codes = [
        '20',
        '21',
        '22',
        '23',
        '25',
        '26'
    ]

    if not isinstance(subject_code, basestring) or \
            not re.match('^\d\d$', subject_code):
        raise ValidationError((_('Invalid subject code.'),))

    if isinstance(product_type_code, basestring):
        if product_type_code not in valid_product_codes:
            error_message = 'Invalid product type code. ' \
                            'Expected one of {codes!r}'.format(
                                codes=valid_product_codes,
                            )
            raise ValidationError((_(error_message),))

    i = 0
    n = 1
    product_sequence_number = 1
    while i < n:
        lc = ckanapi.LocalCKAN()
        results = lc.action.package_search(
            q='product_id_new:{subject_code}{product_type_code}????'.format(
                subject_code=subject_code,
                product_type_code=product_type_code
            ),
            sort='product_id_new ASC',
            rows=1000,
            start=i*1000
        )
        n = results['count'] / 1000.0
        i += 1
        for result in results['results']:
            if product_sequence_number < int(result['product_id_new'][5:8]):
                return (
                    u'{subject_code}'
                    '{product_type_code}'
                    '{sequence_number}'
                ).format(
                    subject_code=subject_code,
                    product_type_code=product_type_code,
                    sequence_number=unicode(product_sequence_number).zfill(4)
                )
            else:
                product_sequence_number += 1

    return u'{subject_code}{product_type_code}{sequence_number}'.format(
        subject_code=subject_code,
        product_type_code=product_type_code,
        sequence_number=unicode(product_sequence_number).zfill(4)
    )


def next_article_id(top_parent_id, issue_number):
    """
    Get next available product ID

    :param top_parent_id:
    :type top_parent_id: 8 digit str
    :param issue_number
    :type issue_number: 7 digit str
    :return: 19 or 20 digit str
    """
    if not isinstance(top_parent_id, basestring) or len(top_parent_id) != 8:
        raise ValidationError(
            (_('Invalid top parent ID. Expected 8 digit string'),)
        )
    if not isinstance(issue_number, basestring) or len(issue_number) != 7:
        raise ValidationError(
            (_('Invalid issue number. Expected 7 digit string'),)
        )

    i = 0
    n = 1
    article_sequence_number = 1
    while i < n:
        lc = ckanapi.LocalCKAN()
        results = lc.action.package_search(
            q='type:article AND '
              'product_id_new:{top_parent_id}{issue_number}*'.format(
                top_parent_id=top_parent_id,
                issue_number=issue_number
              ),
            sort='product_id_new ASC',
            rows=1000,
            start=i*1000
        )
        if results['count'] == 0:
            return u'{top_parent_id}{issue_number}{sequence_number}'.format(
                top_parent_id=top_parent_id,
                issue_number=issue_number,
                sequence_number=unicode(article_sequence_number).zfill(5)
            )

        n = results['count'] / 1000.0
        i += 1
        for result in results['results']:
            old_id = int(result['product_id_new'][15:])
            article_sequence_number = max(
                article_sequence_number,
                old_id
            )

    return (
        u'{top_parent_id}'
        '{issue_number}'
        '{sequence_number}'
    ).format(
        top_parent_id=top_parent_id,
        issue_number=issue_number,
        sequence_number=unicode(article_sequence_number + 1).zfill(5)
    )


def ensure_release_exists(product_id, context=None, ref_period=None):
    """
    Ensure that a release exists for the given product_id.

    :param product_id: The parent product ID.
    :type product_id: str
    :param context: The CKAN request context (if it exists)
    :type context: dict or None
    :param ref_period: The (data) reference period for the release, if one
                       exists.
    """
    # FIXME: the following test is a kludge which exits if loading from ckanapi
    #        need to at least compare to site_id instead of fixed value stcndm
    if context['auth_user_obj'].name == u'stcndm':
        return

    # This is a stub pending the implementation of the external service.


def get_parent_content_types(product_id):
    """
    Return content_type_codes for parent publication of product_id

    :param product_id:
    :type product_id: str
    :return: list
    """
    lc = ckanapi.LocalCKAN()
    results = lc.action.package_search(
        q='product_id_new:{parent_id}'.format(parent_id=product_id[:8])
    )
    if 'results' in results and len(results['results']) == 1:
        return results['results'][0].get(u'content_type_codes', [])
    else:
        return []


def set_previous_issue_archive_date(product_id, archive_date):
    """
    Set the archive date of the previous issue of product_id

    :param product_id:
    :type product_id: str
    :param archive_date:
    :type archive_date: datetime.datetime
    :return:
    """
    if len(product_id) < 15:
        raise ValidationError((_('{product_id}: expected product ID and issue '
                                 'number'.format(product_id=product_id)),))
    lc = ckanapi.LocalCKAN()
    results = lc.action.package_search(
        q='product_id_new:{parent_id}???????'.format(
            parent_id=product_id[:8]
        ),
        sort='product_id_new desc'
    )
    for result in results['results']:
        if result['product_id_new'] < product_id:
            if not result.get('archive_date'):
                result['archive_date'] = archive_date
                lc.action.package_update(**result)
                return
