import contextlib
import logging
import os
import sys
from time import sleep

import git

from .cluster_system import ClusterSubmissionHook
from .utils import rm_dir_full


def sanitize_for_latex(string):
    """Escape characters that have special meaning in latex."""
    # first replace backslashes, so we don't mess up the following escapes
    sanitized = string.replace("\\", r"\textbackslash ")

    # list of replacements is based on https://tex.stackexchange.com/a/34586
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde ",
        "^": r"\textasciicircum ",
    }
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)

    return sanitized


def get_git_url():
    logger = logging.getLogger("cluster_utils")
    try:
        repo = git.Repo(search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
        return None

    url_list = list(repo.remotes.origin.urls)
    if url_list:
        logger.info(f"Auto-detected git repository with remote url: {url_list[0]}")
        return url_list[0]

    return None


def make_git_params(user_git_params, local_path):
    if user_git_params is None:
        git_params = {}
    else:
        git_params = user_git_params.copy()

    git_params["local_path"] = local_path

    if "url" not in git_params:
        auto_url = get_git_url()
        if not auto_url:
            raise git.exc.InvalidGitRepositoryError(
                "No git repository given in json file or auto-detected"
            )

        git_params["url"] = auto_url

    return git_params


class GitConnector(object):
    """
    Class that provides meta information for git repository
    """

    def __init__(
        self,
        local_path=None,
        url=None,
        branch=None,
        depth=None,
        commit=None,
        remove_local_copy=True,
    ):
        self._local_path = local_path  # local working path
        self._orig_url = url  # if given, make local copy of repo in local working path
        self._repo = None
        self._remove_local_copy = remove_local_copy

        if "git" not in sys.modules:
            return

        # make local copy of repo
        if self._orig_url is not None:
            self._make_local_copy(branch, depth, commit)

        self._init()

    def _init(self):
        """
        Import library in a non-breaking fashion, connect to git repo
        :return: None
        """
        # Here we ignore the exception, should not affect of execution of the script
        with contextlib.suppress(git.exc.InvalidGitRepositoryError):
            self._repo = self._connect_local_repo(self._local_path)

    def _connect_local_repo(self, local_path):
        """
        Connects to local repo
        :param path: path to local repo
        :return: git.Repo object
        """

        repo = None
        try:
            repo = git.Repo(path=local_path, search_parent_directories=True)
        except git.exc.InvalidGitRepositoryError as e:
            path = os.getcwd() if self._local_path is None else self._local_path
            msg = (
                "Could not find git repository at localtion {} or any of the parent"
                " directories".format(path)
            )
            raise git.exc.InvalidGitRepositoryError(msg) from e
        except Exception:
            raise

        return repo

    def _get_remote_meta(self, remote_name):
        """
        Returns meta information about specified remote
        :param remote_name: Name of the remote
        :return: Dict containing handle to git. Remote object (or None if not existing)
            and string containing url to remote
        """

        try:
            remote_handle = self._repo.remote(remote_name)
        except Exception:
            remote_handle = None

        remote_url = "" if remote_handle is None else remote_handle.url

        return {"remote_handle": remote_handle, "remote_url": remote_url}

    def _get_commit_meta(self, commit):
        """
        Returns meta information for given commit
        :param commit: handle to git.Commit object
        :return: Dict with commit meta information
        """

        res = dict()
        res["checkout_commit_hexsha"] = commit.hexsha
        res["checkout_commit_hexsha_short"] = self._repo.git.rev_parse(
            res["checkout_commit_hexsha"], short=7
        )
        res["checkout_commit_author"] = sanitize_for_latex(commit.author.name)
        res["checkout_commit_date"] = commit.authored_datetime.strftime("%Y-%m-%d")
        res["checkout_commit_msg"] = sanitize_for_latex(commit.summary)

        return res

    def _get_latex_template(self):
        """
        Returns string containing latex template that is used to produce formatted output
        :return: String containing latex template
        """

        template = """\\begin{{tabular}}{{ l l }}
    Use local copy: & {use_local_copy}\\\\
    Working dir: & {working_dir}\\\\
    Origin: & {origin_url}\\\\
    Active branch: & {active_branch}\\\\
    Commit: & {checkout_commit_hexsha_short}
        (from {checkout_commit_author} on {checkout_commit_date})\\\\
    ~ & {checkout_commit_msg}
\\end{{tabular}}"""

        return template

    def _make_local_copy(self, branch="master", depth=None, commit=None):
        """
        Clones local working copy of the repo to avoid side effects

        Exceptions that are thrown here, should be somehow handeled

        :param url: path to local git repo or url to remote repo
        :param copy_to_path: location in which repo is cloned
        :param branch: branch to clone from
        :param commit: checkout particular commit
        :return: None
        """

        remote_url = self._orig_url
        logger = logging.getLogger("cluster_utils")

        # if url is local path, get url of origin from repo
        if os.path.exists(self._orig_url):
            try:
                local_repo = self._connect_local_repo(self._orig_url)
            except git.exc.InvalidGitRepositoryError:
                raise

            try:
                remote = local_repo.remote("origin")
            except ValueError as e:
                msg = "Remote 'origin' does not exists in repo at {}".format(
                    self._orig_url
                )
                raise ValueError(msg) from e

            remote_url = remote.url

        depth_message = f"depth {depth}" if depth is not None else "full depth"
        logger.info(
            f"Create local git clone of {remote_url} in {self._local_path} using branch"
            f" {branch}, {depth_message} and commit"
            f" {commit if commit else 'latest'} ... "
        )

        cloned_repo = git.Repo.clone_from(
            remote_url, self._local_path, branch=branch, depth=depth
        )

        if commit is not None:
            try:
                # Hard reset HEAD to specific commit
                cloned_repo.head.reset(commit=commit, working_tree=True)
            except git.exc.GitCommandError as e:
                raise RuntimeError(
                    f"Commit {commit} failed as a valid revision. "
                    f"Maybe it is not reachable within depth {depth}?"
                ) from e

    def remove_local_copy(self):
        logger = logging.getLogger("cluster_utils")
        if self._orig_url and self._remove_local_copy:
            logger.info("Remove local git clone in {} ... ".format(self._local_path))
            self._repo.close()
            sleep(1.0)
            git.rmtree(self._local_path)
            rm_dir_full(self._local_path)

    @property
    def meta_information(self):
        logger = logging.getLogger("cluster_utils")

        if self._repo is None:
            logger.warning("Not connected to a git repository")
            return

        res = dict(
            use_local_copy="{}{}".format(
                self._orig_url is not None,
                " (removed after done)" if self._remove_local_copy else "",
            ),
            working_dir=self._repo.working_dir,
            origin_url=self._get_remote_meta("origin")["remote_url"],
            active_branch=self._repo.active_branch.name,
        )
        res.update(self._get_commit_meta(self._repo.commit(res["active_branch"])))

        return res

    @property
    def formatted_meta_information(self):
        return self._get_latex_template().format(**self.meta_information)


class ClusterSubmissionGitHook(ClusterSubmissionHook):
    def __init__(self, params, paths):
        logger = logging.getLogger("cluster_utils")
        self.params = params
        self.git_conn = None
        self.paths = paths

        super().__init__(identifier="GitConnector")

        if self.state > 0:
            logger.warning(
                f'Couldn\'t find git repo in {self.params["local_path"]} and no url to'
                " git repo specified, skipping registration of"
                f" {self.identifier} submission hook"
            )

    def determine_state(self):
        self.state = 1

        if "url" in self.params:
            self.state = 0
        else:
            # Check if local Path is git repo
            try:
                git.Repo(path=self.params["local_path"], search_parent_directories=True)
                self.state = 0
            except Exception:
                pass

    def pre_run_routine(self):
        logger = logging.getLogger("cluster_utils")
        self.git_conn = GitConnector(**self.params)
        if "url" in self.params and self.params.get("commit", None) is None:
            commit_hexsha = self.git_conn._repo.commit(
                self.git_conn._repo.active_branch.name
            ).hexsha
            commit_hexsha_short = self.git_conn._repo.git.rev_parse(
                commit_hexsha, short=7
            )
            logger.info("Using commit {} in each iteration".format(commit_hexsha_short))
            self.params["commit"] = commit_hexsha_short
        self.update_status()

        script_full_path = os.path.join(
            self.paths["main_path"], self.paths["script_to_run"]
        )
        if not os.path.isfile(script_full_path):
            raise FileNotFoundError(
                f"{self.paths['script_to_run']} does not exist. Wrong script name?"
            )
        return self.git_conn

    def post_run_routine(self):
        if self.git_conn:
            self.git_conn.remove_local_copy()
            del self.git_conn
            self.git_conn = None

    def update_status(self):
        if self.git_conn:
            self.status = self.git_conn.formatted_meta_information
