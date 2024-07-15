from cluster_utils.base import constants


def flatten_nested_string_dict(nested_dict, prepend=""):
    for key, value in nested_dict.items():
        if not isinstance(key, str):
            raise TypeError("Only strings as keys expected")
        if isinstance(value, dict):
            for sub in flatten_nested_string_dict(
                value, prepend=prepend + str(key) + constants.OBJECT_SEPARATOR
            ):
                yield sub
        else:
            yield prepend + str(key), value
