

import dask.dataframe as dd
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from logging import getLogger
log = getLogger(__name__)


def analyse_responses(responses_csv):

    def _process_patch_ids(patch_ids):
        patch_id_list = list(patch_ids)
        try:
            patch_id_list.remove('_')
        except ValueError:
            pass
        return len(set(patch_id_list))

    final = dd.read_csv(responses_csv, blocksize=50e7,
                        dtype={"idx ": "int32", "patch_id ": "category", \
                               "responses.resp_msg_id": "category", \
                               "responses.parent": "category", \
                               "upstream": "category", \
                               "response_author": "category"}).drop('Unnamed: 0', axis=1)

    author_patch_counts_dask = final[['patch_id', 'response_author']].groupby('response_author')['patch_id'].agg(
        'count')

    author_patch_counts_dask.nlargest(20).compute(). \
        plot(kind='barh', stacked=False, figsize=[10, 8], colormap='hsv')
    plt.title('Top 20 responders by patches reviewed')
    plt.ylabel('Responding authors')
    plt.xlabel('Number of patch responses ')
    plt.tight_layout()
    plt.savefig('author_top20_patch_counts.pdf')
    plt.close()

    upstream_patch_counts_dask = final[['upstream', 'patch_id']].groupby('upstream')['patch_id'].apply(
        _process_patch_ids, meta=pd.Series([], dtype=int))

    log.info("Unique patch ids {}".format(final['patch_id'].nunique().compute(num_workers=20)))

    log.info("Unique upstream commits {}".format(final['upstream'].nunique().compute(num_workers=20)))

    upstream_patch_counts_dask.nlargest(10).compute(). \
        plot(kind='barh', stacked=False, figsize=[10, 5], colormap='hsv')
    plt.title('Top 10 upstreams by number of related patches')
    plt.ylabel('Upstream commits')
    plt.xlabel('Number of patches')
    plt.tight_layout()
    plt.savefig('upstream_top10_patch_counts.pdf')
    plt.close()

    plt.figure(figsize=(10, 7))
    ax = sns.distplot(upstream_patch_counts_dask.compute(), bins=40, kde=False, color='blue', \
                      vertical=False, kde_kws={"clip": (0, 40)}, hist_kws={"range": (0, 40)})
    ax.set_yscale('log')
    plt.title('Upstream Distribution over patches')
    plt.xlabel('patch count')
    plt.ylabel('upstream')
    plt.tight_layout()
    plt.savefig('upstream_dist_patch_counts_40bins.pdf')
    plt.close()

    upstream_response_counts_dask = final[['upstream', 'responses.resp_msg_id']].groupby('upstream')[
        'responses.resp_msg_id'].agg('count')

    upstream_response_counts_dask.nlargest(15).compute(). \
        plot(kind='barh', stacked=False, figsize=[10, 6], colormap='Pastel1')
    plt.title('Top 15 upstream commits by number of responses')
    plt.ylabel('Upstream commits')
    plt.xlabel('Number of responses')
    plt.tight_layout()
    plt.savefig('upstream_top15_response_counts.pdf')
    plt.close()

    plt.figure(figsize=(10, 8))
    ax = sns.distplot(upstream_response_counts_dask.compute(), bins=500, kde=False, color='green',
                      vertical=False, kde_kws={"clip": (0, 500)}, hist_kws={"range": (0, 500)})
    ax.set_yscale('log')
    plt.title('Upstream Distribution over number of responses')
    plt.xlabel('response count')
    plt.ylabel('upstream')
    plt.tight_layout()
    plt.savefig('upstream_dist_response_counts_500bins.pdf')
    plt.close()

    plt.figure(figsize=(10, 8))
    ax = sns.distplot(upstream_response_counts_dask.compute(), bins=200, kde=False, color='blue',
                      vertical=False, kde_kws={"clip": (0, 200)}, hist_kws={"range": (0, 200)})
    ax.set_yscale('log')
    plt.title('Upstream Distribution over responses, 200 bins')
    plt.xlabel('responses')
    plt.ylabel('upstream count')
    plt.tight_layout()
    plt.savefig('upstream_dist_response_counts_200bins.pdf')
    plt.close()

    patch_id_response_counts_dask = final[['patch_id', 'responses.resp_msg_id']].groupby('patch_id')[
        'responses.resp_msg_id'].agg('count')

    plt.figure(figsize=(12, 12))
    ax = sns.distplot(patch_id_response_counts_dask.compute(), bins=500, kde=False, color='orange',
                      vertical=False, kde_kws={"clip": (0, 500)}, hist_kws={"range": (0, 500)})
    ax.set_yscale('log')
    plt.xlabel('response count')
    plt.ylabel('patches')
    plt.title('Patch Distribution over number of responses')
    plt.tight_layout()
    plt.savefig('patch_dist_response_counts_500bins.pdf')
    plt.close()

    # Patch distribution by responses distinguished by with or without matching upstream
    patch_responses_upstream_df = final[['patch_id', 'upstream', 'responses.resp_msg_id']]

    patch_response_without_upstream_dask = patch_responses_upstream_df[
        patch_responses_upstream_df['upstream'].isna() == True]
    patch_response_without_upstream_grouped_dask = patch_response_without_upstream_dask.groupby('patch_id')[
        'responses.resp_msg_id'].agg('count')

    plt.figure(figsize=(11, 10))
    ax = sns.distplot(patch_response_without_upstream_grouped_dask.compute(), kde=False, color='mediumvioletred', \
                      vertical=False)
    ax.set_yscale('log')
    plt.title('Patch (without matching upstream) Distribution over number of responses')
    plt.xlabel('response count')
    plt.ylabel('patches')
    plt.tight_layout()
    plt.savefig('patch_without_upstream_dist_response_counts.pdf')
    plt.close()

    patch_response_with_upstream_dask = patch_responses_upstream_df[
        patch_responses_upstream_df['upstream'].isna() == False]
    patch_response_with_upstream_grouped_dask = patch_response_with_upstream_dask.groupby('patch_id')[
        'responses.resp_msg_id'].agg('count')

    plt.figure(figsize=(11, 10))
    ax = sns.distplot(patch_response_with_upstream_grouped_dask.compute(), kde=False, color='olivedrab',
                      vertical=False)
    ax.set_yscale('log')
    plt.title('Patch (with matching upstream) Distribution over number of responses')
    plt.xlabel('response count')
    plt.ylabel('patches')
    plt.tight_layout()
    plt.savefig('patch_with_upstream_dist_response_counts.pdf')
    plt.close()

    log.info("Saved plots, done!")
