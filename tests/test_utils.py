import pytest

from cluster_utils.server import utils


def test_check_valid_param_name():
    # non-string argument
    with pytest.raises(TypeError):
        utils.check_valid_param_name(13)

    # reserved name
    with pytest.raises(ValueError):
        utils.check_valid_param_name("working_dir")

    # name ending with "__std"
    with pytest.raises(ValueError):
        utils.check_valid_param_name("foo__std")

    # name starting or ending with dot
    with pytest.raises(ValueError):
        utils.check_valid_param_name(".foo")
    with pytest.raises(ValueError):
        utils.check_valid_param_name("foo.")

    # name contains invalid characters
    with pytest.raises(ValueError):
        utils.check_valid_param_name("$foo")
    with pytest.raises(ValueError):
        utils.check_valid_param_name("with space")
    with pytest.raises(ValueError):
        utils.check_valid_param_name("foo/bar")

    # valid names
    utils.check_valid_param_name("foo")
    utils.check_valid_param_name("foo.bar")
    utils.check_valid_param_name("foo_bar")
    utils.check_valid_param_name("foo-bar")
    utils.check_valid_param_name("foo:bar")
    utils.check_valid_param_name("f00b4r")
