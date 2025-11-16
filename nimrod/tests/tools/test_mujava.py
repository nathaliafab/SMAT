
from unittest import TestCase

from nimrod.tests.utils import calculator_mutants_dir
from nimrod.tests.utils import calculator_mutants_log
from nimrod.tests.utils import get_config

from nimrod.tools.mujava import MuJava
from nimrod.tools.java import Java


class TestMuJava(TestCase):

    def setUp(self):
        self.java_home = get_config()['java_home']
        self.java = Java(self.java_home)

    def test_read_log_with_log_dir(self):

        mujava = MuJava(self.java, calculator_mutants_dir())
        mutants_data = mujava.read_log(calculator_mutants_log())

        self.assertEqual('AOI_1', mutants_data[0].mid)
        self.assertEqual('AOI', mutants_data[0].operator)
        self.assertEqual(18, mutants_data[0].line_number)
        self.assertEqual('int_execute(int,int)', mutants_data[0].method)
        self.assertEqual('a + b => a + b++', mutants_data[0].transformation)
        
        self.assertEqual('AOR_1', mutants_data[1].mid)
        self.assertEqual('AOR', mutants_data[1].operator)
        self.assertEqual(18, mutants_data[1].line_number)
        self.assertEqual('int_execute(int,int)', mutants_data[1].method)
        self.assertEqual('a + b => a - b', mutants_data[1].transformation)
       
        self.assertEqual('AOR_2', mutants_data[2].mid)
        self.assertEqual('AOR', mutants_data[2].operator)
        self.assertEqual(18, mutants_data[2].line_number)
        self.assertEqual('int_execute(int,int)', mutants_data[2].method)
        self.assertEqual('a + b => a * b', mutants_data[2].transformation)
       
    def test_read_log_without_log_dir(self):
        mujava = MuJava(self.java, calculator_mutants_dir())
        
        mutants = mujava.read_log()
        self.assertEqual(3, len(mutants))

    def test_not_found_log(self):
        mujava = MuJava(self.java, calculator_mutants_dir())

        with self.assertRaises(SystemExit):
            mujava.read_log('wrong_path')