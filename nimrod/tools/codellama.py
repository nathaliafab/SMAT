import os

from nimrod.tools.suite_generator import Suite, SuiteGenerator
from nimrod.utils import generate_classpath

class Codellama(SuiteGenerator):

    def _get_tool_name(self):
        return "codellama"

    def _test_classes(self):
        classes = []

        for class_file in sorted(get_class_files(self.suite_classes_dir)):
            filename, _ = os.path.splitext(class_file)
            if not filename.endswith('_scaffolding'):
                classes.append(filename.replace(os.sep, '.'))

        return classes

     def _get_suite_dir(self):
        return os.path.join(self.suite_dir, 'codellama-tests')

    def create_method_list(self, methods: "list[str]"):
        rectified_methods = [self.convert_method_signature(
            method) for method in methods]
        return (":").join(rectified_methods)

    def convert_method_signature(self, meth_signature: str) -> str:
        method_return = ""
        try:
            method_return = meth_signature.split(")")[1]
        except Exception as e:
            print(e)
        meth_name = meth_signature[:meth_signature.rfind("(")]
        meth_args = meth_signature[meth_signature.find(
            "(") + 1:meth_signature.rfind(")")].split(",")
        asm_meth_format = self.asm_based_method_method_descriptor(
            meth_args, method_return)

        return meth_name+asm_meth_format

    # See at: https://asm.ow2.io/asm4-guide.pdf -- Section 2.1.3 and 2.1.4
    # Java type Type descriptor
    # boolean Z
    # char C
    # byte B
    # short S
    # int I
    # float F
    # long J
    # double D
    # Object Ljava/lang/Object;
    # int[] [I
    # Object[][] [[Ljava/lang/Object;
    def asm_based_method_method_descriptor(self, method_arguments, method_return):
        result = '('
        for arg in method_arguments:
            arg = arg.strip()
            result = result + self._asm_based_type_descriptor(arg)
        result = result + ')'
        result = result + self._asm_based_type_descriptor(method_return)
        return result

    def _asm_based_type_descriptor(self, arg):
        result = ''
        if '[]' in arg:
            result = result + '['
            arg = arg.replace('[]', '')

        if arg == '':
            result = result + ''
        elif arg == 'int':
            result = result + 'I'
        elif arg == 'float':
            result = result + 'F'
        elif arg == 'boolean':
            result = result + 'Z'
        elif arg == 'char':
            result = result + 'C'
        elif arg == 'byte':
            result = result + 'B'
        elif arg == 'short':
            result = result + 'S'
        elif arg == 'long':
            result = result + 'J'
        elif arg == 'double':
            result = result + 'D'
        elif arg == 'void':
            result = result + 'V'
        elif arg == 'String':
            result = result + 'Ljava/lang/String;'
        else:
            temp = "L" + arg.replace('.', '/') + ';'
            result = result + temp

        return result