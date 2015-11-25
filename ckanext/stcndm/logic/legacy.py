#!/usr/bin/env python
# encoding: utf-8
import ckanapi
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
import arrow
import pprint

_get_or_bust = logic.get_or_bust
_get_action = toolkit.get_action
_ValidationError = toolkit.ValidationError
_NotFound = toolkit.ObjectNotFound
_NotAuthorized = toolkit.NotAuthorized

# This contains logic related to dealing with legacy products
# which are all special cases with business logic that completely
# differs from al new products

def is_legacy_product(product_id):
    return any(c.isalpha() for c in product_id)

@logic.side_effect_free
def get_next_legacy_product_id(context, data_dict):
    """
    Returns the next available ProductId for a legacy product (without registering it).

    This handles all legacy product types except for articles.

    :param parentProduct: Parent product Id
    :type parentProduct: str
    :param issueNumber: (optional) Issue number
    :type productType: str

    :return: next available ProductId
    :rtype: str

    :raises: ValidationError, ObjectNotFound
    """

    VALID_LEGACY_PRODUCT_TYPE_CODES = {'20': 'analytical',
                                       '25': 'PUMF',  # Public Use Microdata File
                                       '26': 'Publication with Repeating Title'}

    lc = ckanapi.LocalCKAN(context=context)
    product_id = _get_or_bust(data_dict, 'parentProduct')

    data_dict['product_id'] = product_id

    product_type = _get_or_bust(data_dict, 'productType')

    if product_type not in VALID_LEGACY_PRODUCT_TYPE_CODES:
        raise _ValidationError('Invalid product type code')

    lc.action.GetProduct(productId=product_id)

    year = arrow.now().format('YYYY')

    product_family = '{product_id}{year}'.format(
        product_id=product_id,
        year=year
    )

    query = {
        'q': 'product_id_new:{product_family}*'.format(
            product_family=product_family
        ),
        'sort': 'product_id_new desc'
    }

    response = _get_action('package_search')(context, query)

    if response['count'] < 1:
        sequence_id = '001'
    else:
        sequence_id = response['results'][0]['product_id_new'][-3:]

    sequence_id = str(int(sequence_id)+1).zfill(3)

    if sequence_id == '999':
            # TODO: implement reusing unused IDs
        raise _ValidationError(
            'All Product IDs for this family have been used. '
            'Reusing IDs is in development.'
        )

    product_id_new = "{product_id}{year}{sequence_id}".format(product_id=product_id,
                                                              year=year,
                                                              sequence_id=sequence_id,
                                                              )
    return product_id_new


@logic.side_effect_free
def get_next_legacy_article_id(context, data_dict):
    """
    Returns the next available ProductId for a legacy product (without registering it).

    This method only handles articles, which have an additional five digit sequqence compared
    to all other legacy product types

    :param parentProduct: Parent product Id
    :type parentProduct: str

    :return: next available ProductId
    :rtype: str

    :raises: ValidationError, ObjectNotFound
    """

    lc = ckanapi.LocalCKAN(context=context)
    product_id = _get_or_bust(data_dict, 'parentProduct')

    data_dict['product_id'] = product_id

    product_family = '{product_id}'.format(
        product_id=product_id,
    )

    query = {
        'q': 'product_id_new:{product_family}* AND type:article'.format(
            product_family=product_family
            ),
        'sort': 'product_id_new desc'
    }

    response = _get_action('package_search')(context, query)

    # pprint.pprint(response)
    # This is the case where we are generating an article for a publication, we need an article id
    # and sequence id, otherwise we just need a sequence id
    if response['count'] < 1:
        article_id = '00001'
    else:
        article_id = response['results'][0]['product_id_new'][-5:]

    article_id = str(int(article_id)+1).zfill(5)

    product_id_new = "{product_id}{article_id}".format(product_id=product_id,
                                                       article_id=article_id)
    return product_id_new


def register_legacy_non_data_product(context, data_dict):
    """
    Register a new non data product belonging to a product family which hasa a legacy id (i.e. 83-001-X).

    To register anything oth an article belonging to a main product, pass in the top parent id, otherwise
    pass in the issue number to which the article should belong (i.e. 83-001-X2015001

    :param productTitle: EN/FR title dictionary
    :type productTitle: dict
    :param productType: product type code
    :type productType: str
    :param parentProduct:
    :type parentProduct: str

    :return: newly-registered product id
    :rtype: dict
    """
    # These are the only product types that can be registered using
    # this method as these are the only "non-data products".
    # TODO: Can we pull this from somewhere? Presets.yaml does not
    #       necessarily have the exact schema name in ndm_product_type.

    VALID_DATA_TYPES =  {'20': 'set below',
                         '25': 'pumf',  # Public Use Microdata File
                         '26': 'pwrt'}

    title = _get_or_bust(data_dict, 'productTitle')
    product_type = _get_or_bust(data_dict, 'productType')
    parent_product = _get_or_bust(data_dict, 'parentProduct')

    if product_type not in VALID_DATA_TYPES:
        raise _ValidationError(
            'Invalid non data productType, only non data products may be'
            ' registered with this service'
        )

    if not is_legacy_product(parent_product):  # only legacy products have alpha characters in the id
        raise _ValidationError('This service only applies to legacy products'
                               ' please use RegisterNonDataProduct')

    # business logic to identify dataset_type - dofferent types share the same dataset type code
    # TODO: we need to confirm that this is completely correct and that we don't need additional dataset types
    if product_type == '20':
        if len(parent_product) > 8:
            dataset_type = 'article'  # everything other than articles only passes in the top parent id
        elif parent_product[2] == 'F' and parent_product[7] == 'G':
            dataset_type = 'publication' #guide
        elif parent_product[2] == 'F':
            dataset_type = 'publication'
        elif parent_product[7] == 'P':
            dataset_type = 'publication'
        elif parent_product[-1] == 'X':
            dataset_type = 'publication'
    else:
        dataset_type = VALID_DATA_TYPES[product_type]

    lc = ckanapi.LocalCKAN(context=context)

    # We only generate article ids for articles, everything else has a more standard format

    if dataset_type == 'article':
        response = lc.action.GetNextLegacyArticleId(**{'parentProduct': parent_product,
                                                       'productType': product_type})
        product_id_new = response
        issue_number = product_id_new[:-5]
        parent_product = product_id_new[:8]
    else:
        response = lc.action.GetNextLegacyProductId(**{'parentProduct': parent_product,
                                                       'productType': product_type})

        product_id_new = response
        issue_number = product_id_new  # Just for clarity's sake

    product_dict = {
        u'owner_org': u'statcan',
        u'private': False,
        u'type': dataset_type,
        u'issue_number': issue_number,
        u'product_type_code': product_type,
        u'product_id_new': product_id_new,
        u'parent_product': parent_product,
        u'title_translated': title,
        u'top_parent_id': parent_product,
        u'name': u'{dataset_type}-{product_id}'.format(
            dataset_type=dataset_type,
            product_id=product_id_new.lower()
        )
    }

    lc.action.package_create(**product_dict)
    return lc.action.GetProduct(**{'productId': product_id_new})


def is_legacy_id(product_id):
    """
    Test whether passed product_id is in legacy format.

    If it contains anything but digits, it's in legacy format.

    :param product_id: PID
    :type product_id
    :return: boolean
    :raises: ValidationError
    """
    if not isinstance(product_id, basestring):
        raise _ValidationError(('Expecting PID in unicode form',))
    if len(product_id) < 8:
        raise _ValidationError(('PID should be at least 8 characters long',))
    try:
        int(product_id)
        return False
    except ValueError:
        return True
