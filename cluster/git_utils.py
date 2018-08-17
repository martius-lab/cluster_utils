import sys
import os
import shutil
from warnings import warn

try:
    import git
except:
    warn('Could not import git. Please install GitPython if you want to include git meta information in your report')

class GitConnector(object):
    '''
    Class that provides meta information for git repository
    '''

    def __init__(self, path=None, url=None, branch=None, commit=None, remove_local_copy=True):
        self._local_path = path # local working path
        self._orig_url = url # if given, make local copy of repo in local working path
        self._repo = None
        self._remove_local_copy = remove_local_copy

        if 'git' not in sys.modules:
            return

        # make local copy of repo
        if self._orig_url is not None:
            self._make_local_copy(branch, commit)

        self._init()

    def _init(self):
        '''
        Import library in a non-breaking fashion, connect to git repo
        :return: None
        '''

        try:
            self._repo = self._connect_local_repo(self._local_path)
        except git.exc.InvalidGitRepositoryError:
            # Here we ignore the exception, should not affect of execution of the script
            pass

    def _connect_local_repo(self, local_path):
        '''
        Connects to local repo
        :param path: path to local repo
        :return: git.Repo object
        '''

        repo = None
        try:
            repo = git.Repo(path=local_path, search_parent_directories=True)
        except git.exc.InvalidGitRepositoryError as e:
            path = os.getcwd() if self._local_path is None else self._local_path
            warn('Could not find git repository at localtion {} or any of the parent directories'.format(path))
            raise
        except Exception as e:
            raise

        return repo

    def _get_remote_meta(self, remote_name):
        '''
        Returns meta information about specified remote
        :param remote_name: Name of the remote
        :return: Dict containing handle to git.Remote object (or None if not existing) and string containing
                 url to remote
        '''

        try:
            remote_handle = self._repo.remote(remote_name)
        except:
            remote_handle = None

        remote_url = '' if remote_handle is None else remote_handle.url

        return {'remote_handle': remote_handle, 'remote_url': remote_url}

    def _get_commit_meta(self, commit):
        '''
        Returns meta information for given commit
        :param commit: handle to git.Commit object
        :return: Dict with commit meta information
        '''

        res = dict()
        res['checkout_commit_hexsha'] = commit.hexsha
        res['checkout_commit_hexsha_short'] = self._repo.git.rev_parse(res['checkout_commit_hexsha'],
                                                                       short=7)
        res['checkout_commit_author'] = commit.author.name
        res['checkout_commit_date'] = commit.authored_datetime.strftime('%Y-%m-%d')
        res['checkout_commit_msg'] = commit.summary

        return res

    def _get_latex_template(self):
        '''
        Returns string containing latex template that is used to produce formatted output
        :return: String containing latex template
        '''

        template = '''\\begin{{tabular}}{{ l l }}
    Use local copy: & {use_local_copy}\\\\
    Working dir: & {working_dir}\\\\
    Origin: & {origin_url}\\\\
    Active branch: & {active_branch}\\\\
    Commit: & {checkout_commit_hexsha_short} (from {checkout_commit_author} on {checkout_commit_date})\\\\
    ~ & {checkout_commit_msg}
\end{{tabular}}'''

        return template

    def _make_local_copy(self, branch='master', commit=None):
        '''
        Clones local working copy of the repo to avoid side effects

        Exceptions that are thrown here, should be somehow handeled

        :param url: path to local git repo or url to remote repo
        :param copy_to_path: location in which repo is cloned
        :param branch: branch to clone from
        :param commit: checkout particular commit
        :return: None
        '''

        remote_url = self._orig_url

        # if url is local path, get url of origin from repo
        if os.path.exists(self._orig_url):

            try:
                local_repo = self._connect_local_repo(self._orig_url)
            except git.exc.InvalidGitRepositoryError:
                raise

            try:
                remote = local_repo.remote('origin')
            except ValueError:
                warn('Remote \'origin\' does not exists in repo at {}'.format(self._orig_url))
                raise

            remote_url = remote.url

        print('Create local git clone of {} in {} using branch {} and commit {}...'.format(remote_url,
                                                                                           self._local_path,
                                                                                           branch,
                                                                                           commit if commit else 'latest'), end='')

        cloned_repo = git.Repo.clone_from(remote_url, self._local_path, branch=branch)

        if commit is not None:
            # Hard reset HEAD to specific commit
            cloned_repo.head.reset(commit=commit)

        print('Done')

    def remove_local_copy(self):
        if self._orig_url and self._remove_local_copy:
            print('Remove local git clone in {}...'.format(self._local_path), end='')
            shutil.rmtree(self._local_path)
            print('Done')

    @property
    def meta_information(self):

        if self._repo is None:
            warn('Not connected to a git repository')
            return

        res = dict()
        res['use_local_copy'] = str(self._orig_url is not None) + ' (removed after done)' if self._remove_local_copy else ''
        res['working_dir'] = self._repo.working_dir
        res['origin_url'] = self._get_remote_meta('origin')['remote_url']
        res['active_branch'] = self._repo.active_branch.name
        res.update(self._get_commit_meta(self._repo.commit(res['active_branch'])))

        return res

    @property
    def formatted_meta_information(self):

        return self._get_latex_template().format(**self.meta_information)
