from unittest import TestCase

import os

from nimrod.tests.utils import get_config
from nimrod.tests.utils import calculator_project_dir
from nimrod.tests.utils import calculator_clean_project
from nimrod.tests.utils import calculator_target_dir

from nimrod.utils import get_files, get_class_files, get_java_files
from nimrod.utils import generate_classpath
from nimrod.tools.java import Java
from nimrod.tools.maven import Maven


class TestUtils(TestCase):

    def setUp(self):
        self.java_home = get_config()['java_home']
        self.maven_home = get_config()['maven_home']

        self.java = Java(self.java_home)
        self.maven = Maven(self.java, self.maven_home)

        self.maven.compile(calculator_project_dir(), 20)

    def test_get_files(self):
        classes = get_files(calculator_target_dir())

        self.assertEqual(8, len(classes))
        self.assertTrue(('maven-status/maven-compiler-plugin/compile/'
                         + 'default-compile/inputFiles.lst') in classes)
        self.assertTrue(('maven-status/maven-compiler-plugin/compile/'
                         + 'default-compile/createdFiles.lst') in classes)
        self.assertTrue('classes/br/ufal/ic/easy/Calculator.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Sum.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Operation.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Div.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Sub.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Mul.class'
                        in classes)

    def test_get_class_files(self):
        classes = get_class_files(calculator_target_dir())

        self.assertEqual(6, len(classes))
        self.assertTrue('classes/br/ufal/ic/easy/Calculator.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Sum.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Operation.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Div.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Sub.class'
                        in classes)
        self.assertTrue('classes/br/ufal/ic/easy/operations/Mul.class'
                        in classes)

    def test_get_java_files(self):
        classes = get_java_files(os.path.join(calculator_project_dir(), 'src',
                                              'main', 'java'))

        self.assertEqual(6, len(classes))
        self.assertTrue('br/ufal/ic/easy/Calculator.java'
                        in classes)
        self.assertTrue('br/ufal/ic/easy/operations/Sum.java'
                        in classes)
        self.assertTrue('br/ufal/ic/easy/operations/Div.java'
                        in classes)
        self.assertTrue('br/ufal/ic/easy/operations/Operation.java'
                        in classes)
        self.assertTrue('br/ufal/ic/easy/operations/Sub.java'
                        in classes)
        self.assertTrue('br/ufal/ic/easy/operations/Mul.java'
                        in classes)

    def test_generate_classpath(self):
        path = generate_classpath(['a', 'b', 'c'])
        path_split = path.split(os.pathsep)
        self.assertEqual('a', path_split[0])
        self.assertEqual('b', path_split[1])
        self.assertEqual('c', path_split[2])

    def test_generate_classpath_with_invalid_paths(self):
        path = generate_classpath(['a', None, 'b', '', 'c'])
        path_split = path.split(os.pathsep)
        self.assertEqual('a', path_split[0])
        self.assertEqual('b', path_split[1])
        self.assertEqual('c', path_split[2])

    def tearDown(self):
        calculator_clean_project()
