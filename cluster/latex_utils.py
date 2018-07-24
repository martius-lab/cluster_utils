import datetime
import os
from shutil import copyfile
from subprocess import run, PIPE
from tempfile import TemporaryDirectory
from warnings import warn
import sys

def subsection(section_name, content):
  begin = '\\begin{{subsection}}{{{}}}\n'.format(section_name)
  end = '\\end{subsection}\n'
  return '{}\n\\leavevmode\n\n\\medskip\n{}{}'.format(begin, content, end)


def add_subsection_from_figures(section_name, file_list, common_scale=0.7):
  content = '\n'.join([include_figure(filename, common_scale) for filename in file_list])
  return subsection(section_name, content)


def include_figure(filename, scale=1.0):
  return '\\includegraphics[scale={}]{{\detokenize{{{}}}}}\n'.format(scale, filename)


def section(section_name, content):
  begin = '\\begin{{section}}{{{}}}\n'.format(section_name)
  end = '\\end{section}\n'
  return '{}{}{}'.format(begin, content, end)


class LatexFile(object):
  def __init__(self, title):
    self.title = title
    self.date = str(datetime.datetime.today()).split()[0]
    self.sections = []

  def add_section_from_figures(self, name, list_of_filenames, common_scale=1.0):
    begin = '\\begin{center}'
    end = '\\end{center}'
    content = '\n'.join([begin] + [include_figure(filename, common_scale) for filename in list_of_filenames] + [end])
    self.sections.append(section(name, content))

  def add_subsection_from_figures(self, section_name, file_list, common_scale=1.0):
    content = '\n'.join([include_figure(filename, common_scale) for filename in file_list])
    return self.sections.append(subsection(section_name, content))

  def add_section_from_dataframe(self, name, dataframe):
    self.sections.append(section(name, dataframe.to_latex()))

  def add_section_from_python_script(self, name, python_file):
    with open(python_file) as f:
      raw = f.read()
    content = '\\begin{{lstlisting}}[language=Python]\n {}\\end{{lstlisting}}'.format(raw)
    self.sections.append(section(name, content))

  def add_section_from_git(self, name='Git Meta Information'):
    """
    Adds section with git meta information to the output

    :return: None
    """

    try:
      import git
    except:
      warn("Could't import git. Please install GitPython if you want to include git meta information in your report")
      return

    try:
      script_path = os.path.dirname(os.path.realpath(__file__))
      with open(os.path.join(script_path,'assets/latex/git.tex'), 'r') as f:
        latex_template = f.read()
    except:
      warn("Couldn't find latex tamplet git.tex in assets/latex. Git meta information will not be included in your report")
      return

    try:
      repo = git.Repo(search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
      return
    except:
      print(sys.exc_info()[0])
      raise


    working_dir = repo.working_dir
    origin_url = ''
    try:
      origin = repo.remote('origin')
      origin_url = origin.url
    except:
      pass

    active_branch = repo.active_branch.name

    active_commit = repo.commit(active_branch)
    commit_hexsha = active_commit.hexsha
    commit_hexsha_short = repo.git.rev_parse(commit_hexsha, short=7)
    commit_author = active_commit.author.name
    commit_date = active_commit.authored_datetime.strftime('%Y-%m-%d')
    commit_msg = active_commit.summary

    content = latex_template.format(working_dir=working_dir,
                                    origin=origin_url,
                                    active_branch=active_branch,
                                    commit_hexsha_short=commit_hexsha_short,
                                    commit_author=commit_author,
                                    commit_date=commit_date,
                                    commit_msg=commit_msg,
                                   )

    self.sections.append(section(name, content))

  def produce_pdf(self, output_file):
    full_content = '\n'.join(self.sections)
    title_str = LATEX_TITLE.format(self.title)
    date_str = LATEX_DATE.format(self.date)
    whole_latex = '\n'.join([LATEX_BEGIN, title_str, date_str, full_content, LATEX_END])
    with TemporaryDirectory() as tmpdir:
      latex_file = os.path.join(tmpdir, 'latex.tex')
      with open(latex_file, 'w') as f:
        f.write(whole_latex)
      run(['pdflatex', latex_file], cwd=tmpdir, check=True, stdout=PIPE)
      output_tmp = os.path.join(tmpdir, 'latex.pdf')
      copyfile(output_tmp, output_file)


def latex_format(string):
  return string.replace('_', '-')


LATEX_BEGIN = '''
\\documentclass{amsart}
\\usepackage{graphicx}
\\usepackage{framed}
\\usepackage{verbatim}
\\usepackage{booktabs}
\\usepackage{url}
\\usepackage{underscore}
\\usepackage{listings}
\\usepackage{mdframed}
\\usepackage[margin=1.0in]{geometry}

\\usepackage{color}

\\definecolor{codegreen}{rgb}{0,0.6,0}
\\definecolor{codegray}{rgb}{0.5,0.5,0.5}
\\definecolor{codepurple}{rgb}{0.58,0,0.82}
\\definecolor{backcolour}{rgb}{0.95,0.95,0.92}

\\lstdefinestyle{mystyle}{
    backgroundcolor=\\color{backcolour},
    commentstyle=\\color{codegreen},
    keywordstyle=\\color{magenta},
    numberstyle=\\tiny\\color{codegray},
    stringstyle=\\color{codepurple},
    basicstyle=\\footnotesize,
    breakatwhitespace=false,
    breaklines=true,
    captionpos=b,
    keepspaces=true,
    numbers=left,
    numbersep=5pt,
    showspaces=false,
    showstringspaces=false,
    showtabs=false,
    tabsize=2
}

\\lstset{style=mystyle}

\\graphicspath{{./figures/}}
\\newtheorem{theorem}{Theorem}[section]
\\newtheorem{conj}[theorem]{Conjecture}
\\newtheorem{lemma}[theorem]{Lemma}
\\newtheorem{prop}[theorem]{Proposition}
\\newtheorem{cor}[theorem]{Corollary}
\\def \\qbar {\\overline{\\mathbb{Q}}}
\\theoremstyle{definition}
\\newtheorem{definition}[theorem]{Definition}
\\newtheorem{example}[theorem]{Example}
\\newtheorem{xca}[theorem]{Exercise}
\\theoremstyle{remark}
\\newtheorem{remark}[theorem]{Remark}
\\numberwithin{equation}{section}
\\begin{document}\n
'''

LATEX_TITLE = '\\title{{{}}}\n'
LATEX_DATE = '\\date{{{}}}\n \\maketitle\n'
LATEX_END = '\\end{document}'
