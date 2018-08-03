import sys
import os
from warnings import warn

class GitConnector(object):
    '''
    Class that provides meta information for git repository
    '''

    def __init__(self, path=None):
        self._path = path
        self._repo = None

        self._init()

    def _init(self):
        '''
        Import library in a non-breaking fashion, connect to git repo
        :return: None
        '''

        try:
            import git
        except:
            warn('Could not import git. Please install GitPython if you want to include git meta information in your report')
            return

        try:
            self._repo = git.Repo(path=self._path, search_parent_directories=True)
        except git.exc.InvalidGitRepositoryError:
            path = os.getcwd() if self._path is None else self._path
            warn('Could not find git repository at localtion {} or any of the parent directories'.format(path))
            return
        except:
            print(sys.exc_info()[0])
            raise

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
    Working dir: & {working_dir}\\\\
    Origin: & {origin_url}\\\\
    Active branch: & {active_branch}\\\\
    Commit: & {checkout_commit_hexsha_short} (from {checkout_commit_author} on {checkout_commit_date})\\\\
    ~ & {checkout_commit_msg}
\end{{tabular}}'''

        return template

    @property
    def meta_information(self):

        if self._repo is None:
            warn('Not connected to a git repository')
            return

        res = dict()
        res['working_dir'] = self._repo.working_dir
        res['origin_url'] = self._get_remote_meta('origin')['remote_url']
        res['active_branch'] = self._repo.active_branch.name
        res.update(self._get_commit_meta(self._repo.commit(res['active_branch'])))

        return res

    @property
    def formatted_meta_information(self):

        return self._get_latex_template().format(**self.meta_information)
