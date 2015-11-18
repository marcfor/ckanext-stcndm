import json
import ckanapi
from massage_product import do_product

__author__ = 'marc'

release_dict = {}
rc = ckanapi.RemoteCKAN('http://ndmckanq1.stcpaz.statcan.gc.ca/zj/')
i = 0
n = 1
while i < n:
    query_results = rc.action.package_search(
        q='producttypecode_bi_strs:11',
        rows=1000,
        sort='productidnew_bi_strs ASC',
        start=i*1000
    )
    i += 1
    n = query_results['count'] / 1000.0
    for line in query_results['results']:
        for e in line['extras']:
            line[e['key']] = e['value']

        product_out = do_product(line)
        product_out['type'] = u'view'
        product_out['name'] = u'{type}-{product_id}'.format(
                type=product_out['type'],
                product_id=product_out['product_id_new']
            ).lower()
        url_dict = {
            'en': line.get('url_en_strs', ''),
            'fr': line.get('url_fr_strs', '')
        }
        if url_dict['en'] or url_dict['fr']:
            product_out['url_translated'] = url_dict

        print json.dumps(product_out)

        # if product_out['product_id_new'] in release_dict:
        #     release_dict[product_out['product_id_new']] += 1
        # else:
        #     release_dict[product_out['product_id_new']] = 1
        # line['release_id'] = unicode(release_dict[product_out['product_id_new']])
        #
        # release_out = do_release(line)
        # print json.dumps(release_out)

        # format_out = do_format(line)
        # format_out['parent_slug'] = product_out['name']
        # print json.dumps(format_out)
