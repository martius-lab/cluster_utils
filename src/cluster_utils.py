"""
 Utility functions

"""

import os
import collections
import itertools
import random

__docformat__ = 'restructedtext en'


def iter_over_dict_options(dict_of_lists):
    headers = sorted(dict_of_lists.keys())
    values = [dict_of_lists[item] for item in headers]
    for item in itertools.product(*values):
        yield dict(zip(headers, item))


def iter_over_dict_samples(dict_of_lists, how_many_samples):
    for i in range(how_many_samples):
        yield {key: random.choice(value) for key,value in dict_of_lists.iteritems()}


def flatten_strings(iterable):
    for el in iterable:
        if isinstance(el, collections.Iterable) and not isinstance(el, str):
            for subel in flatten_strings(el):
                yield subel
        else:
            yield el


#
def create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)


def concat_files_without_header(working_dir, file_signature, output_file):
    abs_file_signature = os.path.join(working_dir, file_signature)
    abs_output_file = os.path.join(working_dir, output_file)
    abs_tmp_file = os.path.join(working_dir, 'tmpfile')
    return ['head -n 1 {} > {}'.format(abs_file_signature, abs_tmp_file),
            'tail -1 {} > {}'.format(abs_tmp_file, abs_output_file),
            'tail -q -n +2 {} >> {}'.format(abs_file_signature, abs_output_file),
            'rm -f {}'.format(abs_tmp_file),
            'rm -f {}'.format(abs_file_signature)]


def remove_empty_files_from_dir(dir_name):
    return 'find {} -size 0 -print0 | xargs -0 rm -f'.format(dir_name)


def delete_folder_content(folder):
    for the_file in os.listdir(folder):
        file_path = os.path.join(folder, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(e)
