#!/usr/bin/env python
# encoding: utf-8
import json
import datetime
from ckan.logic import _, ValidationError, NotFound
from ckan.lib.navl.dictization_functions import missing
from ckanext.stcndm import helpers as h
from ckanext.stcndm.logic.cubes import get_next_cube_id
from ckanext.stcndm.logic.common import get_next_product_id
from ckan.lib.helpers import lang as lang
from ckanext.stcndm.logic.legacy import is_legacy_id, get_next_legacy_article_id
import re
import ckan.lib.navl.dictization_functions as df
import ckanapi

from ckanext.scheming.validation import (
        scheming_validator, validators_from_string)
from ckanext.fluent.validators import fluent_text_output

LANG_SUFFIX = '_translated'

@scheming_validator
def fluent_core_translated_transitional_output(field, schema):
    assert field['field_name'].endswith(LANG_SUFFIX), ('Output validator '
        '"fluent_core_translated" must only used on a field that ends with '
        '"_translated"')

    def validator(key, data, errors, context):
        """
        Return a value for a core field using a multilingual dict.
        """
        data[key] = fluent_text_output(data[key])

        k = key[-1]
        new_key = key[:-1] + (k[:-len(LANG_SUFFIX)],)

        if new_key in data:
            data[new_key] = data[key]

    return validator

def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9\-_]", "_", name)


def scheming_validator(fn):
    """
    Decorate a validator that needs to have the scheming fields
    passed with this function. When generating navl validator lists
    the function decorated will be called passing the field
    and complete schema to produce the actual validator for each field.
    """
    fn.is_a_scheming_validator = True
    return fn


def shortcode_validate(key, data, errors, context):
    """
    Accept shortcodes in the following forms
    and convert to a json list for storage:

    1. a list of strings, eg.

       ["code-one", "code-two"]

    2. a single string value with semicolon-separated values

       "code-one;code-two"

    """
    # just in case there was an error before our validator,
    # bail out here because our errors won't be useful
    if errors[key]:
        return

    value = data[key]
    if value is missing:
        data[key] = json.dumps([])
        return

    if isinstance(value, basestring):
        if not value:
            data[key] = json.dumps([])
            return
        try:
            if isinstance(json.loads(value), list):
                return
        except ValueError:
            pass  # value wasn't in json format, keep processing
        except TypeError:
            # FIXME should we return missing instead? or
            data[key] = json.dumps([])
            return
        value = value.split(';')

    if not isinstance(value, list):
        errors[key].append(_('expecting list of strings'))
        return

    out = []
    for element in value:
        if not isinstance(element, basestring):
            errors[key].append(_('invalid type for shortcode: %r') % element)
            continue
        if isinstance(element, str):
            try:
                element = element.decode('utf-8')
            except UnicodeDecodeError:
                errors[key].append(_('invalid encoding for "%s" value') % lang)
                continue
        out.append(element.strip())

    # TODO: future: check values against valid choices for this field
    # using @scheming_validator decorator to get the form field name

    if not errors[key]:
        data[key] = json.dumps(out)


def shortcode_output(value):
    """
    Return stored json representation as a list, if
    value is already a list just pass it through.
    """
    if isinstance(value, list):
        return value
    if value is None or value is missing:
        return []
    try:
        return json.loads(value)
    except ValueError:
        return [value]


def _data_lookup(key, data):
    value = None
    if key in data:
        value = data[key]
    else:
        i = 0
        while True:
            extra_key = ('extras', i, 'key')
            if extra_key not in data:
                break
            if data[extra_key] == key:
                value = data[('extras', i, 'value')]
            i += 1
    if isinstance(value, basestring):
        return value.strip()
    else:
        return value


def _data_update(value, key, data):
    data[key] = value
    for data_key in data:
        if data[data_key] == key[0]:
            data[('extras', data_key[1], 'value')] = value


def codeset_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    codeset_type = _data_lookup(('codeset_type',), data)
    codeset_value = _data_lookup(('codeset_value',), data).lower()
    if codeset_type and codeset_value:
        current_name = _data_lookup(('name',), data)
        new_name = u'{0}-{1}'.format(codeset_type, codeset_value.lower())
        if current_name.endswith(u'-clone') or not current_name:
            if not current_name.startswith(new_name):
                data[key] = new_name
    else:
        errors[key].append(_('could not find codeset_type or codeset_value'))


def format_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return
    # if a name has already been set
    # we don need to do it again
    name = data.get(key, u'')
    if name.endswith(u'-clone'):
        format_code = u'0'
        data[('format_code',)] = u'0'
        name = u''
    else:
        format_code = _data_lookup(('format_code',), data)
    if not format_code:
        errors[('format_code',)].append(_('Missing value'))
        errors[key].append(_('Name could not be generated'))
        return

#    if name is missing or not name:
    parent_id = _data_lookup(('parent_id',), data)
    if not parent_id:
        errors[('parent_id',)].append(_('Missing value'))
        errors[key].append(_('Name could not be generated'))
        return

    format_id = u'{parent_id}_{format_code}'.format(
        parent_id=parent_id.lower(),
        format_code=format_code.zfill(2).lower()
    )
    _data_update(format_id, ('format_id',), data)
    data[key] = u'format-{format_id}'.format(
        format_id=format_id
    )
    _data_update(data[key], ('title',), data)


def format_create_id(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return
    # if a name has already been set
    # we don need to do it again
    if data.get(key) is not missing and len(data.get(key, '')):
        return

    parent_id = _data_lookup(('parent_id',), data)
    if not parent_id:
        errors[key].append(_('could not find parent_id of parent'))
    format_code = _data_lookup(('format_code',), data)
    if not format_code:
        errors[key].append(_('could not find format_code'))
    if errors[key]:
        return

    data[key] = u'{0}_{1}'.format(
        parent_id.lower(),
        format_code.zfill(2).lower()
    )


def create_product_id(key, data, errors, context):
    general_non_data_types = (
        u'publication',
        u'video',
        u'conference',
        u'service',
        u'pumf',
        u'generic'
    )
    general_data_types = (
        u'view',
        u'indicator',
        u'chart'
    )
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key] or errors[('subject_codes',)] or errors[('top_parent_id',)]:
        return

    # product_id_new = _data_lookup(('product_id_new',), data)
    # if product_id_new:
    #     return
    data_set_type = _data_lookup(('type',), data)
    # make sure subject_codes processed
    shortcode_validate(('subject_codes',), data, errors, context)
    subject_codes = shortcode_output(_data_lookup(('subject_codes',), data))
    top_parent_id = _data_lookup(('top_parent_id',), data)

    if data_set_type in general_non_data_types:
        try:
            product_id_new = h.next_non_data_product_id(
                subject_code=subject_codes[0][:2],
                product_type_code=_data_lookup(('product_type_code',), data)
            )
            data[key] = product_id_new
            return product_id_new
        except ValidationError as ve:
            errors[('subject_codes',)].append(_(ve.error_summary[u'Message']))
            errors[key].append(_('PID could not be generated'))
            return
        except IndexError:
            errors[('subject_codes',)].append(_('Missing value'))
            errors[key].append(_('PID could not be generated'))
            return
    elif data_set_type == u'article':
        if not top_parent_id:
            errors[('top_parent_id',)].append(_('Missing value'))
            errors[key].append(_('PID could not be generated'))
            return
        issue_number = _data_lookup('issue_number', data)
        if not issue_number:
            errors[('issue_number',)].append(_('Missing value'))
            errors[key].append(_('PID could not be generated'))
            return
        try:
            if is_legacy_id(top_parent_id):
                product_id_new = get_next_legacy_article_id(
                    context=context,
                    data_dict={
                        'parentProduct': u'{top_parent_id}{issue_number}'
                                         .format(
                                            top_parent_id=top_parent_id,
                                            issue_number=issue_number
                                         )
                        }
                )
            else:
                product_id_new = h.next_article_id(
                    top_parent_id=top_parent_id,
                    issue_number=issue_number
                )
            data[key] = product_id_new
            return product_id_new
        except ValidationError as ve:
            errors[key].append(_(ve))
            return
    elif data_set_type == u'cube':
        try:
            product_id_new = get_next_cube_id(
                context=context,
                data_dict={'subjectCode': subject_codes[0][:2]}
            )
            data[key] = product_id_new
            return product_id_new
        except ValidationError as ve:
            errors[('subject_codes',)].append(_(ve.error_dict['message']))
            errors[key].append(_('PID could not be generated'))
            return
        except IndexError:
            errors[('subject_codes',)].append(_('Missing value'))
            errors[key].append(_('PID could not be generated'))
            return
    elif data_set_type in general_data_types:
        if not top_parent_id or top_parent_id is missing:
            errors[('top_parent_id',)].append(_('Missing value'))
            errors[key].append(_('PID could not be generated'))
            return
        try:
            product_id_new = get_next_product_id(
                context,
                {
                    'parentProductId': top_parent_id,
                    'productType': data.get((u'product_type_code',))
                }
            )
            data[key] = product_id_new
            return product_id_new
        except ValidationError as ve:
            errors[('top_parent_id',)].append(ve.error_dict['message'])
            errors[key].append(_('PID could not be generated'))
            return
        except NotFound as e:
            errors[('top_parent_id',)].append(e[0])
            errors[key].append(_('PID could not be generated'))
            return
    else:
        errors[key].append(_(
            'create_product_id not yet implemented for {data_set_type}'.format(
                data_set_type=data_set_type
            )
        ))

    return


def subject_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    subject_code = _data_lookup(('subject_code',), data)
    if subject_code:
        current_name = _data_lookup(('name',), data)
        new_name = u'subject-{0}'.format(subject_code.lower())
        if current_name.endswith(u'-clone') or not current_name:
            if not current_name.startswith(new_name):
                data[key] = new_name
    else:
        errors[key].append(_('could not find subject_code'))


def province_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    sgc_code = _data_lookup(('sgc_code',), data)
    if sgc_code:
        current_name = _data_lookup(('name',), data)
        new_name = u'province-{0}'.format(sgc_code.lower())
        if current_name.endswith(u'-clone') or not current_name:
            if not current_name.startswith(new_name):
                data[key] = new_name
    else:
        errors[key].append(_('could not find sgc_code'))


def set_default_value(default_value):
    # if there was an error before calling our validator
    # don't bother with our validation

    def validator(key, data, errors, context):
        if errors[key]:
            return
        if isinstance(default_value, basestring):
            data[key] = default_value

    return validator


def survey_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    product_id_new = _data_lookup(('product_id_new',), data)
    if product_id_new:
        current_name = _data_lookup(('name',), data)
        new_name = u'survey-{0}'.format(product_id_new.lower())
        if current_name.endswith(u'-clone') or not current_name:
            if not current_name.startswith(new_name):
                data[key] = new_name
    else:
        errors[key].append(_('could not find product_id_new'))


def correction_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    product_id_new = _data_lookup(('product_id_new',), data)
    correction_id = _data_lookup(('correction_id',), data)
    if not product_id_new:
        errors[key].append(_('could not find product_id_new'))
    elif not correction_id:
        errors[key].append(_('could not find correction_id'))
    else:
        data[key] = (u'correction-{product_id}_{correction_id}'.format(
            product_id=product_id_new,
            correction_id=correction_id
        )).lower()


def next_correction_id(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    data[key] = h.next_correction_id()


def product_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    existing_name = _data_lookup(('name',), data)
    if existing_name is missing or not existing_name or \
            existing_name.endswith(u'-clone'):
        create_product_id(('product_id_new',), data, errors, context)
        if errors[('product_id_new',)]:
            errors[key].append(_('Name could not be generated'))
            return
        product_id_new = _data_lookup(('product_id_new',), data)
        data_set_type = _data_lookup(('type',), data)
        if product_id_new:
            data[key] = u'{data_set_type}-{product_id_new}'.format(
                data_set_type=data_set_type,
                product_id_new=product_id_new.lower()
            )
        else:
            errors[('product_id_new',)].append(_('Missing value'))
            errors[key].append(_('Name could not be generated'))


def daily_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    product_id_new = _data_lookup(('product_id_new',), data)
    if product_id_new:
        current_name = _data_lookup(('name',), data)
        new_name = u'daily-{0}'.format(product_id_new.lower())
        if (
                current_name.endswith(u'-clone') and
                not current_name.startswith(new_name)
        ) or not current_name:
                data[key] = new_name
    else:
        errors[('product_id_new',)].append(_('Missing value'))
        errors[key].append(_('Name could not be generated'))


def ndm_str2boolean(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    truth_values = ['true', 'yes', 'y', '1']

    if isinstance(data[key], bool):
        return

    if data[key] is missing or data[key].lower() not in truth_values:
        data[key] = False
    else:
        data[key] = True


def geodescriptor_create_name(key, data, errors, context):
    # if there was an error before calling our validator
    # don't bother with our validation
    if errors[key]:
        return

    geodescriptor_code = _data_lookup(('geodescriptor_code',), data)
    if geodescriptor_code:
        current_name = _data_lookup(('name',), data)
        new_name = safe_name(
            u'geodescriptor-{0}'.format(geodescriptor_code.lower())
        )
        if current_name.endswith(u'-clone') or not current_name:
            if not current_name.startswith(new_name):
                data[key] = new_name
    else:
        errors[('geodescriptor_code',)].append(_('Missing value'))
        errors[key].append(_('Name could not be generated'))


@scheming_validator
def codeset_multiple_choice(field, schema):
    """
    Accept zero or more values from a list of choices and convert
    to a json list for storage:

    1. a list of strings, eg.:

       ["choice-a", "choice-b"]

    2. a single string for single item selection in form submissions:

       "choice-a"
    """

    def validator(key, data, errors, context):
        # if there was an error before calling our validator
        # don't bother with our validation
        if errors[key]:
            return

        codeset_type = field['codeset_type']
        codeset_choices = h.codeset_choices(codeset_type)
        value = _data_lookup(key, data)
        if value is missing:
            value = []
        elif isinstance(value, basestring):
            value = [value]
        elif isinstance(value, list):
            for element in value:
                if not isinstance(element, basestring):
                    errors[key].append(_('expecting list of strings'))
                    return
        else:
            errors[key].append(_('expecting list of strings'))
            return

        selected = set()  # store in a set to eliminate duplicates
        for element in value:
            if element in codeset_choices:
                selected.add(element)
            else:
                errors[key].append(_('unexpected choice "%s"') % element)

        if not errors[key]:
            result = json.dumps(list(selected))
            data[key] = result

    return validator


def ndm_tag_name_validator(value, context):

    tag_name_match = re.compile('[\w \-.,:\'/()]*$', re.UNICODE)
    if not tag_name_match.match(value):
        raise df.Invalid(_(
            'Tag "%s" must be alphanumeric characters or'
            ' symbols: - _ . , : \' / ( )'
        ) % value)
    return value


def apply_archive_rules(key, data, errors, context):
    if errors[key]:
        return
    release_date = _data_lookup(key, data)
    if release_date:
        archive_date = _data_lookup((u'archive_date',), data)
        content_type_codes = _data_lookup((u'content_type_codes',), data)
        product_type_code = _data_lookup((u'product_type_code',), data)
        product_id_new = _data_lookup((u'product_id_new',), data)
        if product_type_code == u'24':
            if not archive_date:
                _data_update(
                    release_date+datetime.timedelta(days=2*365),
                    (u'archive_date',),
                    data
                )
        elif product_type_code == u'20':
            if not content_type_codes:
                content_type_codes = h.get_parent_content_types(
                    product_id_new
                )
            if not content_type_codes:
                errors[(u'content_type_codes',)].append(_('Missing value'))
                errors[(u'archive_date',)].append(_('Unable to determine'))
                return
            # Analysis/Stats in brief
            if u'2016' in content_type_codes:
                if not archive_date:
                    _data_update(
                        release_date+datetime.timedelta(days=5*365),
                        (u'archive_date',),
                        data
                    )
            # Analysis/Articles and Reports
            elif u'2021' in content_type_codes:
                if not archive_date:
                    _data_update(
                        release_date+datetime.timedelta(days=5*365),
                        (u'archive_date',),
                        data
                    )
            # # Reference
            # elif content_type_code in [u'2002', u'2003', u'2023']:
            #     set_archive_date()
            # # Reference/Classification
            elif u'2025' in content_type_codes and len(product_id_new) >= 15:
                try:
                    h.set_previous_issue_archive_date(
                        product_id_new,
                        release_date+datetime.timedelta(days=5*365)
                    )
                except ValidationError as e:
                    errors[(u'product_id_new',)].append(
                        _(e.error_summary[u'Message']))
                    errors[(u'archive_date',)].append(_('Unable to determine'))
