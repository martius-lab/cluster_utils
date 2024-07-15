from __future__ import annotations

import datetime
import logging
import os
import pathlib
import typing
from abc import ABC, abstractmethod
from shutil import copyfile
from subprocess import PIPE, CalledProcessError, run
from tempfile import TemporaryDirectory


def subsection(section_name, content):
    begin = "\\begin{{subsection}}{{{}}}\n".format(section_name)
    end = "\\end{subsection}\n"
    return "{}\n\\leavevmode\n\n\\medskip\n{}{}".format(begin, content, end)


def add_subsection_from_figures(section_name, file_list, common_scale=0.7):
    content = "\n".join(
        [include_figure(filename, common_scale) for filename in file_list]
    )
    return subsection(section_name, content)


def include_figure(filename, scale_linewidth=1.0):
    return "\\includegraphics[width={}\\linewidth]{{\\detokenize{{{}}}}}\n".format(
        scale_linewidth, filename
    )


def section(section_name, content):
    begin = "\\begin{{section}}{{{}}}\n".format(section_name)
    end = "\\end{section}\n"
    return "{}{}{}".format(begin, content, end)


class LatexFile(object):
    def __init__(self, title):
        self.title = title
        self.date = str(datetime.datetime.today()).split()[0]
        self.sections = []

    def add_section_from_figures(self, name, list_of_filenames, common_scale=1.0):
        begin = "\\begin{center}"
        end = "\\end{center}"
        content = "\n".join(
            [begin]
            + [include_figure(filename, common_scale) for filename in list_of_filenames]
            + [end]
        )
        self.sections.append(section(name, content))

    def add_subsection_from_figures(self, section_name, file_list, common_scale=1.0):
        content = "\n".join(
            [include_figure(filename, common_scale) for filename in file_list]
        )
        return self.sections.append(subsection(section_name, content))

    def add_section_from_dataframe(self, name, dataframe):
        begin = "\\begin{center}"
        end = "\\end{center}"
        section_content = "\n".join([begin, dataframe.to_latex(), end])
        self.sections.append(section(name, section_content))

    def add_section_from_python_script(self, name, python_file):
        with open(python_file) as f:
            raw = f.read()
        content = (
            "\\begin{{lstlisting}}[language=Python]\n {}\\end{{lstlisting}}".format(raw)
        )
        self.sections.append(section(name, content))

    def add_generic_section(self, name, content):
        self.sections.append(section(name, content))

    def add_section_from_json(self, name, json_file):
        with open(json_file) as f:
            raw = f.read()
        content = "\\begin{{lstlisting}}[language=json]\n {}\\end{{lstlisting}}".format(
            raw
        )
        self.sections.append(section(name, content))

    def produce_pdf(self, output_file: str | os.PathLike) -> None:
        """Construct the LaTeX file and generate a PDF from it (using pdflatex).

        In case pdflatex fails with an error, the LaTeX file is saved to ``{{
        output_file }}.tex`` and the log to `{{ output_file }}.log`` for offline
        debugging.  If there is no error, those files are automatically deleted when
        finished.

        Args:
            output_file: Path to which the PDF file is written.
        """
        logger = logging.getLogger("cluster_utils")

        output_file = pathlib.Path(output_file)

        full_content = "\n".join(self.sections)
        title_str = LATEX_TITLE.format(self.title)
        date_str = LATEX_DATE.format(self.date)
        whole_latex = "\n".join(
            [LATEX_BEGIN, title_str, date_str, full_content, LATEX_END]
        )
        with TemporaryDirectory() as tmpdir:
            latex_file = os.path.join(tmpdir, "latex.tex")
            with open(latex_file, "w") as f:
                f.write(whole_latex)
            logger.info(f"pdflatex call started on {latex_file}")
            try:
                run(
                    ["pdflatex", "-interaction=nonstopmode", latex_file],
                    cwd=tmpdir,
                    check=True,
                    stdout=PIPE,
                )
            except CalledProcessError as e:
                # save the log and tex for debugging
                logger.error(
                    "pdflatex failed with exit code %d.  Save log and tex file for"
                    " debugging.",
                    e.returncode,
                )
                latex_log_file = os.path.join(tmpdir, "latex.log")
                copyfile(latex_file, output_file.with_suffix(".tex"))
                copyfile(latex_log_file, output_file.with_suffix(".log"))

                # re-raise the error
                raise

            output_tmp = os.path.join(tmpdir, "latex.pdf")
            try:
                copyfile(output_tmp, output_file)
            except FileNotFoundError as e:
                logger.error(
                    "Expected that pdflatex produced output file %s but file does not"
                    " exist.",
                    e.filename,
                )
                raise
            logger.info("Report is saved as %s", output_file)


def latex_format(string):
    return string.replace("_", "-")


class StaticSectionGenerator:
    """
    Section generator (for use with :class:`SectionHook`) that returns a static value.
    """

    def __init__(self, value: typing.Any) -> None:
        """
        Args:
            value:  Value that will be returned when calling the instance.
        """
        self.value = value

    def __call__(self, df, path_to_results, filename_generator):
        return self.value


class SectionHook(ABC):
    def __init__(self, *, section_title, section_generator):
        self.title = section_title
        self.generator = section_generator

    def write_section(self, latex_object, filename_generator, generator_args):
        section_content = self.generator(
            **generator_args, filename_generator=filename_generator
        )
        self.add_section(latex_object, section_content)

    @abstractmethod
    def add_section(self, latex_object, section_content):
        pass


class SectionFromFiguresHook(SectionHook):
    def __init__(self, *, figure_scale=1.0, **kwargs):
        super().__init__(**kwargs)
        self.figure_scale = figure_scale

    def add_section(self, latex_object, section_content):
        latex_object.add_section_from_figures(
            self.title, section_content, common_scale=self.figure_scale
        )


class SectionFromJsonHook(SectionHook):
    def add_section(self, latex_object, section_content):
        latex_object.add_section_from_json(name=self.title, json_file=section_content)


class SectionFromPyHook(SectionHook):
    def add_section(self, latex_object, section_content):
        latex_object.add_section_from_python_script(self.title, section_content)


class SectionFromDataframeHook(SectionHook):
    def add_section(self, latex_object, section_content):
        latex_object.add_section_from_dataframe(self.title, section_content)


LATEX_BEGIN = r"""
\documentclass{amsart}
\usepackage{graphicx}
\usepackage{framed}
\usepackage{verbatim}
\usepackage{booktabs}
\usepackage{url}
\usepackage{underscore}
\usepackage{listings}
\usepackage{mdframed}
\usepackage[margin=1.0in]{geometry}

\usepackage{color}
\usepackage{xcolor}

\definecolor{eclipseStrings}{RGB}{42,0.0,255}
\definecolor{eclipseKeywords}{RGB}{127,0,85}
\colorlet{numb}{magenta!60!black}

\lstdefinelanguage{json}{
    basicstyle=\normalfont\ttfamily,
    commentstyle=\color{eclipseStrings}, % style of comment
    stringstyle=\color{eclipseKeywords}, % style of strings
    numbers=left,
    numberstyle=\scriptsize,
    stepnumber=1,
    numbersep=8pt,
    showstringspaces=false,
    breaklines=true,
    frame=lines,
    backgroundcolor=\color{white}, %only if you like
    string=[s]{"}{"},
    comment=[l]{:\ "},
    morecomment=[l]{:"},
    literate=
        *{0}{{{\color{numb}0}}}{1}
         {1}{{{\color{numb}1}}}{1}
         {2}{{{\color{numb}2}}}{1}
         {3}{{{\color{numb}3}}}{1}
         {4}{{{\color{numb}4}}}{1}
         {5}{{{\color{numb}5}}}{1}
         {6}{{{\color{numb}6}}}{1}
         {7}{{{\color{numb}7}}}{1}
         {8}{{{\color{numb}8}}}{1}
         {9}{{{\color{numb}9}}}{1}
}

\definecolor{codegreen}{rgb}{0,0.6,0}
\definecolor{codegray}{rgb}{0.5,0.5,0.5}
\definecolor{codepurple}{rgb}{0.58,0,0.82}
\definecolor{backcolour}{rgb}{0.95,0.95,0.92}

\lstdefinestyle{mystyle}{
    backgroundcolor=\color{backcolour},
    commentstyle=\color{codegreen},
    keywordstyle=\color{magenta},
    numberstyle=\tiny\color{codegray},
    stringstyle=\color{codepurple},
    basicstyle=\footnotesize,
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

\lstset{style=mystyle}

\graphicspath{{./figures/}}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{conj}[theorem]{Conjecture}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{prop}[theorem]{Proposition}
\newtheorem{cor}[theorem]{Corollary}
\def \qbar {\overline{\mathbb{Q}}}
\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{example}[theorem]{Example}
\newtheorem{xca}[theorem]{Exercise}
\theoremstyle{remark}
\newtheorem{remark}[theorem]{Remark}
\numberwithin{equation}{section}
\begin{document}

"""

LATEX_TITLE = "\\title{{{}}}\n"
LATEX_DATE = "\\date{{{}}}\n \\maketitle\n"
LATEX_END = "\\end{document}"
