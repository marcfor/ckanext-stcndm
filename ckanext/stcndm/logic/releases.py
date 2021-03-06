# --coding: utf-8 --
import ckanapi
import datetime
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
import ckanext.stcndm.helpers as stcndm_helpers
import pylons.config as config
import json
from ckanext.stcndm.helpers import to_utc, default_release_date

_get_or_bust = logic.get_or_bust
_stub_msg = {
    'result': 'This method is just a stub for now. Please do not use.'
}
_ValidationError = toolkit.ValidationError
_NotFound = toolkit.ObjectNotFound
_NotAuthorized = toolkit.NotAuthorized


# noinspection PyIncorrectDocstring
@logic.side_effect_free
def get_releases_for_product(context, data_dict):
    # noinspection PyUnresolvedReferences
    """
    Returns all of the releases for the given `productId`.

    :param productId: ID of the parent product.
    :type productId: str
    """
    product_id = _get_or_bust(data_dict, 'productId')

    lc = ckanapi.LocalCKAN(context=context)

    results = lc.action.package_search(
        q='parent_product:{pid}'.format(pid=product_id)
    )

    return {
        'count': results['count'],
        'results': [r for r in results['results']]
    }


# noinspection PyIncorrectDocstring
def ensure_release_exists(context, data_dict):
    # noinspection PyUnresolvedReferences
    """
    Ensure a release exists for the given `productId`.

    :param productId: The parent product ID.
    :type productId: str
    """
    product_id = _get_or_bust(data_dict, 'productId')
    stcndm_helpers.ensure_release_exists(product_id, context=context)


# noinspection PyIncorrectDocstring
@logic.side_effect_free
def consume_transaction_file(context, data_dict):
    # noinspection PyUnresolvedReferences
    """
    Triggers a background task to start consuming the transaction file.

    :param transactionFile: Daily registration transactions
    :type transactionFile: dict
    """
    try:
        def my_get(a_data_dict, key, expected):
            value = a_data_dict.get(key)
            if not value:
                raise _ValidationError({key: u'Missing value'})
            if not isinstance(value, expected):
                raise _ValidationError(
                    {key: u'Invalid format ({value}), '
                          u'expecting a {type}'.format(
                                value=value,
                                type=expected.__name__)})
            return value

        if u'transactionFile' not in data_dict:
            transaction_ssh_host = config.get(
                'ckanext.stcndm.transaction_ssh_host')
            if not transaction_ssh_host:
                raise _NotFound({
                    u'transactionFile': u'ckanext.stcndm.transaction_ssh_host '
                                        u'missing from CKAN config file'})
            transaction_ssh_user = config.get(
                'ckanext.stcndm.transaction_ssh_user')
            if not transaction_ssh_user:
                raise _NotFound({
                    u'transactionFile': u'ckanext.stcndm.transaction_ssh_user '
                                        u'missing from CKAN config file'})
            transaction_ssh_path = config.get(
                'ckanext.stcndm.transaction_ssh_path')
            if not transaction_ssh_path:
                raise _NotFound({
                    u'transactionFile': u'ckanext.stcndm.transaction_ssh_path '
                                        u'missing from CKAN config file'})
            from paramiko import (SSHClient,
                                  AuthenticationException,
                                  SSHException)
            from socket import gaierror
            client = SSHClient()
            client.load_system_host_keys()
            try:
                client.connect(transaction_ssh_host,
                               username=transaction_ssh_user)
                stdin, stdout, stderr = client.exec_command(
                    'cat '+transaction_ssh_path)
                data_dict = json.loads(stdout.read())
            except gaierror as e:
                raise _NotFound({
                    u'transactionFile': 'Invalid host: ' +
                                        transaction_ssh_host + ' : ' + e[1]
                })
            except ValueError as e:
                raise _ValidationError({
                    u'transactionFile': 'is ' + transaction_ssh_path +
                                        ' the correct path to the '
                                        'transaction file?: ' + e.message
                })
            except AuthenticationException as e:
                raise _NotAuthorized({
                    u'transactionFile': 'ssh ' +
                                        transaction_ssh_user + '@' +
                                        transaction_ssh_host + ' failed: ' +
                                        e.message
                })
            except SSHException as e:
                raise _ValidationError({
                    u'transactionFile': 'ssh mis-configured: ' +
                                        e.message
                })

        transaction_dict = my_get(data_dict, u'transactionFile', dict)
        daily_dict = my_get(transaction_dict, u'daily', dict)
        release_date_text = my_get(daily_dict, u'release_date', basestring)
        releases = my_get(daily_dict, u'release', list)
        lc = ckanapi.LocalCKAN(context=context)
        results = []
        for release in releases:
            if not isinstance(release, dict):
                raise _ValidationError({
                    u'release': u'Invalid format, '
                    u'expecting a list of dict'
                })
            product_id = my_get(release, u'id', basestring)
            letter_id = my_get(release, u'letter_id', basestring)
            stats_in_brief = my_get(release, u'stats_in_brief', basestring)
            title = {
                u'en': my_get(release, u'title_en', basestring),
                u'fr': my_get(release, u'title_fr', basestring)
            }
            reference_period = {
                u'en': release.get(u'refper_en'),
                u'fr': release.get(u'refper_fr')
            }
            theme_list = my_get(release, u'theme', list)
            cube_list = release.get(u'cube', [])
            survey_list = release.get(u'survey', [])
            product_list = release.get(u'product', [])
            url = {
                u'en': u'/daily-quotidien/{release_date}/dq{release_date}'
                       u'{letter_id}-eng.htm'.format(
                         release_date=release_date_text[:10],
                         letter_id=letter_id
                       ),
                u'fr': u'/daily-quotidien/{release_date}/dq{release_date}'
                       u'{letter_id}-fra.htm'.format(
                         release_date=release_date_text[:10],
                         letter_id=letter_id
                       )
            }
            try:
                results.append(lc.action.RegisterDaily(
                    ** {
                        u'releaseDate': to_utc(release_date_text,
                                               def_date=default_release_date),
                        u'productId': u'00240001' + product_id,
                        u'statsInBrief': stats_in_brief,
                        u'productTitle': title,
                        u'referencePeriod': reference_period,
                        u'themeList': theme_list,
                        u'cubeList': cube_list,
                        u'surveyList': survey_list,
                        u'productList': product_list,
                        u'url': url
                    }
                ))
            except _ValidationError as ve:
                results.append({
                    u'product_id_new': u'00240001'+product_id,
                    u'error': ve.error_dict})
        stcndm_helpers.write_audit_log("consume_transaction_file", results)
    except _ValidationError as ve:
        stcndm_helpers.write_audit_log("consume_transaction_file", ve, 3)
        raise ve
    return results
