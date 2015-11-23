#!/usr/bin/env python
# encoding: utf-8
import json
import ckan.plugins as p
import ckanext.stcndm.logic.common as common
import ckanext.stcndm.logic.cubes as cubes
import ckanext.stcndm.logic.daily as daily
import ckanext.stcndm.logic.legacy as legacy
import ckanext.stcndm.logic.releases as releases
import ckanext.stcndm.logic.subjects as subjects
import ckanext.stcndm.logic.views as views
import ckanext.stcndm.logic.surveys as surveys
import datetime
from dateutil.parser import parse

from ckan.lib.navl.dictization_functions import _
from ckan.logic import ValidationError
from ckanext.stcndm import validators
from ckanext.stcndm import helpers
from ckanext.scheming.helpers import (
    scheming_language_text,
    scheming_get_dataset_schema
)
from helpers import lookup_label
import unicodedata


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


class STCNDMPlugin(p.SingletonPlugin):
    p.implements(p.IActions)
    p.implements(p.IConfigurer)
    p.implements(p.IPackageController, inherit=True)
    p.implements(p.IValidators)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IPackageController)
    p.implements(p.IRoutes)
    p.implements(p.IFacets)

    def update_config(self, config):
        """
        Add configuration we need during startup
        """
        p.toolkit.add_template_directory(config, "templates")
        p.toolkit.add_public_directory(config, 'public')

        config.update({
            # TODO: We can probably just make this dynamic? Are there
            #       schemas that should *not* be imported other than presets?
            'scheming.dataset_schemas': '\n'.join([
                'ckanext.stcndm:schemas/article.yaml',
                'ckanext.stcndm:schemas/chart.yaml',
                'ckanext.stcndm:schemas/codeset.yaml',
                'ckanext.stcndm:schemas/conference.yaml',
                'ckanext.stcndm:schemas/corrections.yaml',
                'ckanext.stcndm:schemas/cube.yaml',
                'ckanext.stcndm:schemas/daily.yaml',
                'ckanext.stcndm:schemas/format.yaml',
                'ckanext.stcndm:schemas/generic.yaml',
                'ckanext.stcndm:schemas/geodescriptor.yaml',
                'ckanext.stcndm:schemas/indicator.yaml',
                'ckanext.stcndm:schemas/province.yaml',
                'ckanext.stcndm:schemas/publication.yaml',
                'ckanext.stcndm:schemas/release.yaml',
                'ckanext.stcndm:schemas/pumf.yaml',
                'ckanext.stcndm:schemas/service.yaml',
                'ckanext.stcndm:schemas/subject.yaml',
                'ckanext.stcndm:schemas/survey.yaml',
                'ckanext.stcndm:schemas/video.yaml',
                'ckanext.stcndm:schemas/view.yaml'
            ]),
            'scheming.presets': '\n'.join([
                'ckanext.scheming:presets.json',
                'ckanext.repeating:presets.json',
                'ckanext.fluent:presets.json',
                'ckanext.stcndm:schemas/presets.yaml'
            ])
        })

    def before_index(self, data_dict):
        """
        customize data sent to solr
        """
        bogus_date = datetime.datetime(1, 1, 1)
        dataset_schema = scheming_get_dataset_schema(
            data_dict.get('type', 'unknown')
        )
        if dataset_schema is None:
            error_message = 'Found no schema for following dataset :\n{dump}'\
                .format(
                    dump=json.dumps(data_dict, indent=2)
                    )
            raise ValidationError((_(error_message),))

        # iterate through dataset fields defined in schema
        field_schema = dict()
        for dataset_field in dataset_schema['dataset_fields']:
            d = dataset_field
            field_schema[d['field_name']] = d

        index_data_dict = {}
        authors = []
        # drop extras fields
        for dict_key in data_dict:
            if not dict_key.startswith('extras_'):
                index_data_dict[dict_key] = data_dict[dict_key]
        # iterate through validated data_dict fields and modify as needed
        validated_data_dict = json.loads(data_dict['validated_data_dict'])
        for item in validated_data_dict.keys():
            value = validated_data_dict[item]
            if not value and item in index_data_dict:
                index_data_dict.pop(item)
                continue
            fs = field_schema.get(item, None)
            # ignore all fields not currently in the schema
            if not fs:
                continue

            field_type = fs.get('schema_field_type', 'string')
            multivalued = fs.get('schema_multivalued', False)

            if field_type == 'fluent':
                for key in value.keys():
                    label = u'{item}_{key}'.format(
                        item=item,
                        key=key
                    )
                    index_data_dict[label] = value[key]

            # for code type, the en/fr labels need to be looked up
            # and sent to Solr
            elif field_type == 'code':
                lookup_type = fs.get('lookup', '')
                if lookup_type == 'codeset':
                    lookup = fs.get('codeset_type', '')
                elif lookup_type == 'preset':
                    lookup = fs.get('preset', '')[4:]
                else:
                    lookup = fs.get('lookup', '')
                if lookup and value:
                    label_en = u'{item}_desc_en'.format(
                        item=item
                    )
                    label_fr = u'{item}_desc_fr'.format(
                        item=item
                    )
                    if multivalued:
                        desc_en = []
                        desc_fr = []
                        for v in value:
                            if not v:
                                continue
                            desc = lookup_label(lookup, v, lookup_type)
                            desc_en.append(desc[u'en'])
                            desc_fr.append(desc[u'fr'])

                        index_data_dict[str(item)] = value

                        index_data_dict[label_en] = desc_en
                        index_data_dict[label_fr] = desc_fr
                    else:
                        desc = lookup_label(lookup, value, lookup_type)
                        index_data_dict[label_en] = desc[u'en']
                        index_data_dict[label_fr] = desc[u'fr']
            elif field_type == 'date':
                if value:
                    try:
                        date = parse(value, default=bogus_date)
                        if date != bogus_date:
                            index_data_dict[item] = date.isoformat() + 'Z'
                    except ValueError:
                        continue
            elif item.endswith('_authors'):
                index_data_dict[str(item)] = value
                authors.extend(value)
            else:  # all other field types
                if multivalued:
                    index_data_dict[str(item)] = value
                else:
                    index_data_dict[str(item)] = value

            if authors:
                index_data_dict['authors'] = authors
                index_data_dict['authors_initials'] = list(
                    set(
                        [strip_accents(i[0]).upper() for i in authors]
                    )
                )

        return index_data_dict

    def after_create(self, context, data):
        if 'model' in context:
            # We need to force a commit to get the metadata_modified
            # and metadata_created columns. It is *not* enough for us to
            # simply set these ourselves. This is caused by after_create
            # being called long before creation is actually complete.
            context['model'].repo.commit()

        try:
            helpers.ensure_release_exists(data, context=context)
        except helpers.NotValidProduct:
            pass

    def get_actions(self):
        # Some Java web clients require the web service to use Pascal Case
        return {
            "GetAutocomplete": common.get_autocomplete,
            "DeleteProduct": common.delete_product,
            "EnsureReleaseExists": releases.ensure_release_exists,
            "GetBookableProducts": daily.get_bookable_releases,
            "GetCubeList": cubes.get_cube_list_by_subject,
            "GetCube": cubes.get_cube,
            "GetNextCubeId": cubes.get_next_cube_id,
            "GetNextNonDataProductId": common.get_next_non_data_product_id,
            "CreateOrUpdateCubeRelease": cubes.create_or_update_cube_release,
            "GetThemes": daily.get_themes,
            "GetDailyList": daily.get_daily_list,
            "GetDefaultViews": daily.get_default_views,
            "GetDerivedProductList": common.get_derived_product_list,
            "GetFormatDescription": common.get_format_description,
            "GetLastPublishStatus": common.get_last_publish_status,
            "GetNextProductId": common.get_next_product_id,
            "GetNextLegacyArticleId": legacy.get_next_legacy_article_id,
            "GetNextLegacyProductId": legacy.get_next_legacy_product_id,
            "GetProduct": common.get_product,
            "GetProductIssueArticles": daily.get_product_issue_articles,
            "GetProductIssues": daily.get_product_issues,
            "GetProductType": common.get_product_type,
            "GetRelease": releases.get_release,
            "GetReleasesForProduct": releases.get_releases_for_product,
            "GetSubject": subjects.get_subject,
            "GetSubjectList": subjects.get_top_level_subject_list,
            "GetSurveySubjectCodes": surveys.get_survey_subject_codes,
            "GetUpcomingReleases": common.get_upcoming_releases,
            "GetIssuesByPubStatus": common.get_issues_by_pub_status,
            "GetProductFormats": daily.get_product_formats,
            "PurgeDataset": common.purge_dataset,
            "RegisterCube": cubes.register_cube,
            "RegisterDaily": daily.register_daily,
            "RegisterDataProduct": common.register_data_product,
            "RegisterNonDataProduct": common.register_non_data_product,
            "RegisterLegacyNonDataProduct": legacy.register_legacy_non_data_product,
            "RegisterProduct": common.register_data_product,
            "RegisterRelease": releases.register_release,
            "RegisterSurvey": surveys.register_survey,
            "UpdateDefaultView": views.update_default_view,
            "UpdateParentReleaseDateAndStatus": common.update_parent_release_date_and_status,
            "UpdateProductGeo": common.update_product_geo,
            "UpdatePublishingStatus": common.update_last_publish_status,
            "GetDatasetSchema": common.get_dataset_schema,
            "GetGroupSchema": common.get_group_schema,
            "GetSurveyCodesets": surveys.get_survey_codesets,
            "GetSubjectCodesets": subjects.get_subject_codesets,
            "GetProductsByFRC": daily.get_products_by_frc,
            "ConsumeTransactionFile": releases.consume_transaction_file
        }

    def get_validators(self):
        return {
            "apply_archive_rules": validators.apply_archive_rules,
            "codeset_create_name": validators.codeset_create_name,
            "codeset_multiple_choice": validators.codeset_multiple_choice,
            "correction_create_name": validators.correction_create_name,
            "create_product_id": validators.create_product_id,
            "daily_create_name": validators.daily_create_name,
            "set_default_value": validators.set_default_value,
            "format_create_name": validators.format_create_name,
            "format_create_id": validators.format_create_id,
            "geodescriptor_create_name": validators.geodescriptor_create_name,
            "next_correction_id": validators.next_correction_id,
            "ndm_str2boolean": validators.ndm_str2boolean,
            "ndm_tag_name_validator": validators.ndm_tag_name_validator,
            "province_create_name": validators.province_create_name,
            "product_create_name": validators.product_create_name,
            "shortcode_validate": validators.shortcode_validate,
            "shortcode_output": validators.shortcode_output,
            "subject_create_name": validators.subject_create_name,
            "survey_create_name": validators.survey_create_name,
            "fluent_core_translated_transitional_output": validators.fluent_core_translated_transitional_output
        }

    def get_helpers(self):
        return {
            "codeset_choices": helpers.codeset_choices,
            "lookup_label": helpers.lookup_label,
            "get_dataset_types": helpers.get_dataset_types,
            "get_parent_content_types": helpers.get_parent_content_types,
            "set_previous_issue_archive_date": helpers.set_previous_issue_archive_date,
            'ensure_release_exists': helpers.ensure_release_exists,
            'get_parent_dataset': helpers.get_parent_dataset,
            'get_child_datasets': helpers.get_child_datasets,
            'x2list': helpers.x2list,
        }

    def before_view(self, pkg_dict):
        """
        Ensure that (if available) the correct language strings
        are used for core CKAN fields.
        """
        fields_to_fluent = (
            u'title',
            u'notes'
        )

        for field in fields_to_fluent:
            if field in pkg_dict and isinstance(pkg_dict[field], dict):
                pkg_dict[field] = scheming_language_text(pkg_dict[field])

        return pkg_dict

    def before_map(self, map):
        map.connect(
            'clone',
            '/dataset/clone/{ds_id}',
            controller=(
                'ckanext.stcndm.controllers.clone'
                ':CloneDatasetController'
            ),
            action='clone'
        )

        map.connect(
            'child_dataset',
            '/dataset/{ds_id}/new_child/{ds_type}',
            controller=(
                'ckanext.stcndm.controllers.child_dataset'
                ':ChildDatasetController'
            ),
            action='new'
        )

        map.connect(
            'list',
            '/api/current/list',
            controller=(
                'ckanext.stcndm.controllers.api_ext'
                ':APIExtController'
            ),
            action='list'
        )

        map.connect(
            'solr_proxy',
            '/solr/select',
            controller=(
                'ckanext.stcndm.controllers.solr_proxy'
                ':SolrProxyController'
            ),
            action='select'
        )

        return map

    def after_map(self, map):
        # Required since we implement IRoutes.
        return map

    def dataset_facets(self, facets_dict, package_type):
        return facets_dict

    def organization_facets(self, facets_dict, organization_type,
                            package_type):
        # We always want the dataset type selector to appear.
        # Currently, groups, organizations, licence type, etc... do not
        # apply to ndm, so lets clear the default fields as well.
        facets_dict.clear()
        facets_dict['dataset_type'] = _('Dataset Type')
        return facets_dict

    def group_facets(self, facets_dict, group_type, package_type):
        return facets_dict
