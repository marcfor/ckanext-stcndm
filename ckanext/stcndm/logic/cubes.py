#!/usr/bin/env python
# encoding: utf-8
import ckanapi
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
from ckan.plugins.toolkit import (
    ObjectNotFound,
    ValidationError
)
from ckan.logic import _
import re

_get_or_bust = logic.get_or_bust
_get_action = toolkit.get_action
_NotFound = logic.NotFound

# All cubes are of product type 10.
CUBE_PRODUCT_TYPE = '10'


@logic.side_effect_free
def get_next_cube_id(context, data_dict):
    """
    Returns the next available cube_id (without registering it).

    :param subjectCode: two-digit subjectCode (i.e. '24')
    :type subjectCode: str

    :return: next available cube_id
    :rtype: str

    :raises: ValidationError
    """
    subject_code = _get_or_bust(data_dict, 'subjectCode')
    if not re.match('^\d\d$', subject_code):
        raise ValidationError(_('Invalid subject_code'),)

    lc = ckanapi.LocalCKAN(context=context)
    response = lc.action.package_search(
        q=(
            'product_id_new:{subject_code}10* AND '
            'dataset_type:cube'
        ).format(subject_code=subject_code),
        sort='product_id_new desc',
        rows=1
    )

    if response['results']:
        result = response['results'][0]
        oldest_product_id = result['product_id_new']
        if oldest_product_id.endswith('9999'):
            # FIXME: This system is going to encounter numerous
            #        problems down the road.
            raise ValidationError(
                'All Cube IDs for this subject have been registered.'
                'Reusing IDs is in development.'
            )

        return str(int(oldest_product_id) + 1)

    return '{subject_code}100001'.format(subject_code=subject_code)


@logic.side_effect_free
def get_cube(context, data_dict):
    """
    Return a dict representation of a cube, given a cubeId, if it exists.

    :param cubeId: ID of the cube to retrieve. (i.e. 1310001)
    :type cubeId: str

    :return: requested cube
    :rtype: dict

    :raises: ValidationError, ObjectObjectNotFound
    """
    cube_id = _get_or_bust(data_dict, 'cubeId')
    lc = ckanapi.LocalCKAN(context=context)
    result = lc.action.package_search(
        q=(
            'dataset_type:cube AND '
            'product_id_new:{cube_id}'
        ).format(cube_id=cube_id),
        rows=1
    )

    if not result['count']:
        raise ObjectNotFound('Cube not found')
    elif result['count'] > 1:
        raise ValidationError('More than one cube with given cubeid found')
    else:
        return result['results'][-1]


@logic.side_effect_free
def get_cube_list_by_subject(context, data_dict):
    """
    Return a dict with all Cube Ids and French/English titles based on a
    provided SubjectCode.

    :param subjectCode: two-digit subject code (i.e. 13)
    :type subjectCode: str

    :return: registered cubes for the SubjectCode and their
             French/English titles
    :rtype: list of dicts

    :raises: ValidationError, ObjectObjectNotFound
    """
    subject_code = _get_or_bust(data_dict, 'subjectCode')

    if len(subject_code) != 2:
        raise ValidationError('invalid subjectcode')

    lc = ckanapi.LocalCKAN(context=context)
    result = lc.action.package_search(
        q=(
            'dataset_type:cube AND '
            '(subject_codes:{code} OR '
            'subject_codes:{code}*)'
        ).format(code=subject_code),
        rows=1000
    )

    count = result['count']
    if not count:
        raise ObjectNotFound(
            'Found no cubes with subject code {subject_code}'.format(
                subject_code=subject_code
            )
        )
    else:
        return [{
            u'title': r['title'],
            u'cube_id': r['product_id_new']
        } for r in result['results']]


def register_cube(context, data_dict):
    """
    Register a new cube.  Automatically populate
    subjectcode fields based on provided parameters.

    :param subjectCode: two-digit subject_code code (i.e. 13)
    :type subjectCode: str
    :param productTitleEnglish: english title
    :type productTitleEnglish: unicode
    :param productTitleFrench: french title
    :type productTitleFrench: unicode

    :return: new package
    :rtype: dict

    :raises: ValidationError
    """
    subject_code = _get_or_bust(data_dict, 'subjectCode')
    title_en = _get_or_bust(data_dict, 'productTitleEnglish')
    title_fr = _get_or_bust(data_dict, 'productTitleFrench')

    if not len(subject_code) == 2:
        raise ValidationError('subjectCode not valid')

    lc = ckanapi.LocalCKAN(context=context)

    product_type_dict = lc.action.GetProductType(
        productType=CUBE_PRODUCT_TYPE
    )

    product_id = lc.action.GetNextCubeId(**data_dict)

    lc.action.package_create(
        # Old method simply used the product_id, whereas the modern edit
        # form validator uses cube-{product_id}, so lets go with that.
        owner_org='statcan',
        private=False,
        type=u'cube',
        product_id_new=product_id,
        product_type_code=product_type_dict['product_type_code'],
        subject_codes=[subject_code],
        title_translated={
            'en': title_en,
            'fr': title_fr,
        },
        # '2' is "Draft" status, according to the ndm_publish_status
        # preset.
        last_publish_status_code='2'
    )

    # Return our newly created package.
    return lc.action.GetCube(cubeId=product_id)


def create_or_update_cube_release(context, data_dict):
    """
    Create or add new Cube release(s).

    :param productId: ID of the cube.
    :type productId: str
    :param refPeriod: A list of reference periods.
    :type refPeriod: list
    """
    product_id = _get_or_bust(data_dict, 'productId')
    reference_periods = _get_or_bust(data_dict, 'refPeriod')

    lc = ckanapi.LocalCKAN(context=context)

    product_response = lc.action.package_search(
        q='dataset_type:cube AND product_id_new:{product_id}'.format(
            product_id=product_id
        ),
        rows=1
    )

    if not product_response['count']:
        raise _NotFound('no product with that productId')

    product_result = product_response['results'][0]

    for ref_period in reference_periods:
        # Step A - determine if it's a new release/ref_period
        release_response = lc.action.package_search(
            q=(
                'dataset_type:release'
                ' AND parent_product:{pid}'
                ' AND data_reference_period:{ref_period}'
            ).format(
                pid=product_result['product_id_new'],
                ref_period=ref_period
            ),
            rows=1
        )

        if not release_response['count']:
            # It's a new release/ref_period, do B
            # See DISSNDM-3794 for business logic here.
            # Find the highest release_id.
            release_response = lc.action.package_search(
                q=(
                    'dataset_type:release'
                    ' AND parent_product:{pid}'
                ).format(
                    pid=product_result['product_id_new']
                ),
                rows=1,
                sort='release_id desc'
            )

            if not release_response['count']:
                release_id = '001'
            else:
                release_id = str(
                    int(release_response['results'][0]['release_id'])
                ).zfill(3)

            lc.action.package_create(
                type=u'release',
                release_id=release_id,
                owner_org=product_result['owner_org'],
                parent_product=product_result['product_id_new'],
                publish_status_code='04',
                is_correction='0'
            )
        else:
            # It's an existing release/ref_period, do C
            # See DISSNDM-3794 for business logic here.
            release_result = release_response['results'][0]
            release_result['release_date'] = None
            # "Working Copy" == 04
            release_result['publish_status_code'] = '04'
            lc.action.package_update(**release_result)
