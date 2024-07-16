import cluster_utils.server.cluster_system as cs


def test_is_command_available():
    # test with something we can be pretty sure it's there on any system
    assert cs.is_command_available("ls")

    assert not cs.is_command_available("obscure_command_that_does_not_exist")
