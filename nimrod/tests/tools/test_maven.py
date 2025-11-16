import os
import subprocess

from unittest import TestCase
from nimrod.tests.utils import get_config
from nimrod.tests.utils import calculator_project_dir
from nimrod.tests.utils import calculator_clean_project
from nimrod.tools.java import Java
from nimrod.tools.maven import Maven


class TestMaven(TestCase):

    def setUp(self):
        self.java_home = get_config()['java_home']
        self.maven_home = get_config()['maven_home']
        self.java = Java(self.java_home)

    def test_init_maven_home_not_found(self):
        self._clear_environment()

        with self.assertRaises(SystemExit):
            Maven(java=self.java)

    def test_init_without_parameters(self):
        self._clear_environment()
        os.environ['M2_HOME'] = self.maven_home
        Maven(java=self.java)

        self._clear_environment()
        os.environ['MAVEN_HOME'] = self.maven_home
        Maven(java=self.java)

        self._clear_environment()
        os.environ['MVN_HOME'] = self.maven_home
        Maven(java=self.java)

    def test_init_with_parameter(self):
        Maven(java=self.java, maven_home=self.maven_home)

    def test_init_wrong_maven_home(self):
        self._clear_environment()
        os.environ['MVN_HOME'] = 'wrong_path'
        with self.assertRaises(SystemExit):
            Maven(java=self.java)

    def test_init_wrong_parameter(self):
        self._clear_environment()
        with self.assertRaises(SystemExit):
            Maven(java=self.java, maven_home='wrong_path')

    def test_maven_timeout(self):
        maven = Maven(java=self.java, maven_home=self.maven_home)
        with self.assertRaises(subprocess.TimeoutExpired):
            maven.exec(timeout=0)

    def test_maven_wrong_args(self):
        maven = Maven(java=self.java, maven_home=self.maven_home)
        with self.assertRaises(subprocess.CalledProcessError):
            maven.simple_exec('< x')

    def test_compile_no_maven_project_dir(self):
        maven = Maven(java=self.java, maven_home=self.maven_home)
        with self.assertRaises(subprocess.CalledProcessError):
            maven.compile('.', timeout=10)

    def test_compile_in_maven_project_dir(self):
        project_dir = os.path.join(calculator_project_dir(), '..', 'example')

        calculator_clean_project()

        maven = Maven(java=self.java, maven_home=self.maven_home)
        maven.compile(project_dir, timeout=10)

        self.assertTrue(os.path.exists(os.path.join(project_dir, 'target')))

        calculator_clean_project()

    def test_extract_results(self):
        output = ('0328efjhdaso [INFO] Compiling 6 source files to ' +
                  '/a/b/c/target/classes\n[INFO] 0asdjhaskdjf Compiling')
        results = Maven.extract_results(output)

        self.assertEqual(6, results.source_files)
        self.assertEqual('/a/b/c/target/classes', results.classes_dir)

    @staticmethod
    def _clear_environment():
        if 'M2_HOME' in os.environ:
            del os.environ['M2_HOME']
        if 'MAVEN_HOME' in os.environ:
            del os.environ['MAVEN_HOME']
        if 'MVN_HOME' in os.environ:
            del os.environ['MVN_HOME']
