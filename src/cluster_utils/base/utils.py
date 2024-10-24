import contextlib
import textwrap

from cluster_utils.base import constants


class OptionalDependencyNotFoundError(ModuleNotFoundError):
    """Error to throw if an optional dependency is not found.

    The error message provided by this class is more informative than a generic
    ModuleNotFoundError and also includes the proper pip command to install the missing
    optional dependency.
    """

    def __init__(self, module: str, optional_dependency_group: str) -> None:
        """
        Args:
            module: Name of the module which was not found.
            optional_dependency_group: Name of the optional dependency group which
                should be installed to have the missing package.
        """
        super().__init__(name=module)

        self.message = textwrap.dedent(
            """
            Failed to import '{module}'.  Make sure you installed the optional '{group}' dependencies.
            You can do this with:
            ```
            # when installing directly from git:
            pip install "cluster_utils[{group}]"

            # when installing from local working copy:
            pip install ".[{group}]"
            ```
        """.format(
                module=module, group=optional_dependency_group
            )
        )

    def __str__(self) -> str:
        return self.message


class OptionalDependencyImport(contextlib.AbstractContextManager):
    """Context manager to re-raises ModuleNotFoundError with a more informative message.

    This is to be used for importing packages that are optional dependencies.  It
    catches an eventual import error and re-raises it as OptionalDependencyNotFoundError.
    """

    def __init__(self, dependency_group: str) -> None:
        self.dependency_group = dependency_group

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is ModuleNotFoundError:
            raise OptionalDependencyNotFoundError(
                exc_value.name, self.dependency_group
            ).with_traceback(traceback)


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
