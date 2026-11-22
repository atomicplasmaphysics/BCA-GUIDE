# Prints the failed tests of a JUnit XML file of pytest as GitHub Actions error annotations (continuous integration),
# the annotations are shown on the summary page of a run (python setup/junit_annotations.py junit.xml)

from sys import argv
from xml.etree import ElementTree


def escape(text: str) -> str:
    """
    Escapes a message of an annotation (one line)

    :param text: message
    """

    return text.replace('%', '%25').replace('\r', '').replace('\n', '%0A')


def escapeProperty(text: str) -> str:
    """
    Escapes a property of an annotation (e.g. the title)

    :param text: property
    """

    return escape(text).replace(':', '%3A').replace(',', '%2C')


def main(path: str) -> int:
    """
    Prints the annotations and returns the exit code

    :param path: path of JUnit XML file
    """

    failures = 0
    for case in ElementTree.parse(path).getroot().iter('testcase'):
        for result in list(case.findall('failure')) + list(case.findall('error')):
            failures += 1
            name = f'{case.get("classname", "")}::{case.get("name", "")}'
            details = (result.text or '').strip().splitlines()
            # the end of the traceback contains the error
            message = '\n'.join([result.get('message', '')] + details[-25:])
            print(f'::error title={escapeProperty(name)}::{escape(message[:3000])}')
    print(f'{failures} failed tests')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(argv[1]))
