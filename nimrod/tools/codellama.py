import os

from nimrod.tools.suite_generator import Suite, SuiteGenerator
from nimrod.utils import generate_classpath

class Codellama(SuiteGenerator):

    def _get_tool_name(self):
        return "codellama"

    def _test_classes(self):
        return ['RegressionTest', 'ErrorTest']
