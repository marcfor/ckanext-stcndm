import json
import ckanapi
from massage_product import do_product
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import gettz

__author__ = 'marc'
default_date = datetime(1, 1, 1, 0, 0, 0, 0, tzinfo=gettz('America/Toronto'))
default_release_date = datetime(1, 1, 1, 8, 30, 0, 0,
                                tzinfo=gettz('America/Toronto'))


def to_utc(date_str, def_date=default_date):
    result = parse(date_str, default=def_date)
    utc_result = result.astimezone(gettz('UTC'))
    return utc_result.replace(tzinfo=None).isoformat()


release_dict = {}
rc = ckanapi.RemoteCKAN('http://ndmckanq1.stcpaz.statcan.gc.ca/zj')
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='organization:ndindicator',
        sort='productidnew_bi_strs asc',
        rows=1000,
        start=i*1000)
    n = query_results['count'] / 1000.0
    i += 1

    for line in query_results['results']:
        for e in line['extras']:
            line[e['key'].strip()] = e['value'].strip()

        line['productidnew_bi_strs'] = line.get('productidnew_bi_instrs', '')
        line['subjnewcode_bi_txtm'] = line.get('subjnewcode_bi_intxtm', '')
        line['title_en_txts'] = line.get('title_en_intxts', '')
        line['title_fr_txts'] = line.get('title_fr_intxts', '')
        line['releasedate_bi_strs'] = to_utc(
            line.get('releasedate_bi_instrs'),
            default_release_date)
        line['refperiod_en_txtm'] = line.get('refperiod_en_intxtm', '')
        line['refperiod_fr_txtm'] = line.get('refperiod_fr_intxtm', '')
        line['description_en_txts'] = line.get('description_en_intxts', '')
        line['description_fr_txts'] = line.get('description_fr_intxts', '')

        if line['productidnew_bi_strs'] in release_dict:
            release_dict[line['productidnew_bi_strs']] += 1
        else:
            release_dict[line['productidnew_bi_strs']] = 1
        line['release_id'] = unicode(release_dict[line['productidnew_bi_strs']])

        product_out = do_product(line)
        product_out['product_type_code'] = '12'
        product_out['type'] = u'indicator'
        product_out['name'] = u'{type}-{product_id}'.format(
                type=product_out['type'],
                product_id=product_out['product_id_new']
            ).lower()
        url_dict = {
            'en': line.get('url_en_instrs', ''),
            'fr': line.get('url_fr_instrs', '')
        }
        if url_dict['en'] or url_dict['fr']:
            product_out['url'] = url_dict
        print json.dumps(product_out)

        # release_out = do_release(line)
        # print json.dumps(release_out)
