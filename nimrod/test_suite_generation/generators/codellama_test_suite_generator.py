import os
from typing import Dict, List
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis

from nimrod.test_suite_generation.generators.test_suite_generator import \
    TestSuiteGenerator
from nimrod.tools.java import Java
from nimrod.utils import generate_classpath

from mlc_chat import ChatModule


class CodellamaTestSuiteGenerator(TestSuiteGenerator):
    TARGET_METHODS_LIST_FILENAME = 'methods_to_test.txt'
    TARGET_CLASS_LIST_FILENAME = 'classes_to_test.txt'

    def get_generator_tool_name(self) -> str:
        return "CODELLAMA"

    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        paths = []

        for node in os.listdir(path):
            if os.path.isdir(os.path.join(path, node)):
                paths += self._get_test_suite_class_paths(os.path.join(path, node))
            elif node.endswith(".java"):
                paths.append(os.path.join(path, node))
        
        return paths


    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        class_names = []

        for class_path in self._get_test_suite_class_paths(test_suite_path):
            class_fqcn = os.path.relpath(class_path, os.path.join(
                test_suite_path, "codellama-tests")).replace(os.sep, ".")
            class_names.append(class_fqcn[:-5])

        return class_names

    def _create_method_list(self, methods: "List[str]"):
        rectified_methods = [self._convert_method_signature(
            method) for method in methods]
        return (":").join(rectified_methods)

    def _convert_method_signature(self, meth_signature: str) -> str:
        method_return = ""
        try:
            method_return = meth_signature.split(")")[1]
        except Exception as e:
            print(e)
        meth_name = meth_signature[:meth_signature.rfind("(")]
        meth_args = meth_signature[meth_signature.find(
            "(") + 1:meth_signature.rfind(")")].split(",")
        asm_meth_format = self._asm_based_method_method_descriptor(
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
    def _asm_based_method_method_descriptor(self, method_arguments, method_return):
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

    def generate_prompts(self, prompts_file, class_name, methods, code):
        for method in methods:
            temp_method = method.split("(")[0]

            try:
                with open(code, 'r') as file:
                    lines = file.readlines()

                method_found = False
                method_code = []
                for line in lines:
                    if temp_method in line and ("private" in line or "public" in line):
                        method_found = True
                    elif temp_method not in line and ("private" in line or "public" in line):
                        if method_found:
                            break
                    if method_found:
                        method_code.append(line)

                if method_found:
                    modified_lines = []
                    modified_lines.append(f"/*{''.join(method_code)}*/\n\n")
                    modified_lines.append("import org.junit.FixMethodOrder;\n")
                    modified_lines.append("import org.junit.Test;\n")
                    modified_lines.append("import org.junit.runners.MethodSorters;\n")
                    modified_lines.append("import static org.junit.Assert.*;\n\n")
                    modified_lines.append(f"@FixMethodOrder(MethodSorters.NAME_ASCENDING)\n")
                    modified_lines.append(f"public class {class_name.split('.')[-1]}Test {{\n")
                    modified_lines.append(f"//continue the test with code only:\n")
                    modified_lines.append(f"\"\"\"")
                
                    with open(prompts_file, "w") as file:
                        file.writelines(modified_lines)

            except Exception as e:
                print(f"Error while generating prompt for method {method}: {e}")

    def get_imports(self, code):
        with open(code, 'r') as file:
            lines = file.readlines()

        imports = []
        for line in lines:
            if line.strip().startswith("import"):
                imports.append(line)
            elif line.strip().startswith("package"):
                package_name = line.split()[1].rstrip(';')
                imports.append(f'import {package_name}.*;\n')

        return imports

    def read_prompts(self, file_path):
        prompts = []
        current_prompt = ""

        with open(file_path, "r") as file:
            lines = file.readlines()
            
            for line in lines:
                if line.strip() != '"""':
                    current_prompt += line
                else:
                    if current_prompt.strip() != "":
                        prompts.append(current_prompt)
                        current_prompt = ""

        return prompts

    def create_chat_module(self, mpath, lpath, model, lib):
        return ChatModule(
            model=f"{mpath}/{model}",
            model_lib_path=f"{lpath}/{lib}",
        )


    def generate_output(self, chat_module, prompt):
        return chat_module.generate(prompt=prompt)


    def save_output(self, prompt, output, dir, output_file_name):
        if dir:
            if not os.path.exists(dir):
                os.makedirs(dir)

        output_file_path = f"{dir}/{output_file_name}.java"
        with open(output_file_path, "w") as f:
            f.write(prompt + output)

    def get_branch(self, input_jar, code_base, code_left, code_right, code_merge):
        if 'base' in input_jar:
            return code_base, "base"
        if 'left' in input_jar:
            return code_left, "left"
        if 'right' in input_jar:
            return code_right, "right"
        if 'merge' in input_jar:
            return code_merge, "merge"

    def reset_chat_module(self, chat_module):
        chat_module.reset_chat()

    def change_method_name(self, prompt, method_name):
        new_prompt = prompt.split("public class")[0]
        new_prompt += f"public class {method_name} {{\n"
        return new_prompt

    def get_individual_tests(self, output_path, prompt, class_name, imports, i):
        counter = 0

        if not os.path.exists(f"{output_path}/individual_tests"):
            os.makedirs(f"{output_path}/individual_tests")

        for file in os.listdir(output_path):
            lines = []
            test = []
            open_brackets_count = 0
            test_found = False

            if file.endswith(".java") and file.startswith(f"{i}"):
                with open(os.path.join(output_path, file), "r") as f:
                    lines.extend(f.readlines())

            for j, line in enumerate(lines):
                if "{" in line:
                    open_brackets_count += 1
                
                if "}" in line:
                    open_brackets_count -= 1

                if ("@Test" in line or "import" in line or "package" in line) and test_found:
                    test_found = False
                    method_name = f"{class_name.split('.')[-1]}Test_{i}_{counter}"
                    with open(f"{output_path}/individual_tests/{method_name}.java", "w") as f:
                        full_prompt = "".join(imports) + self.change_method_name(prompt, method_name)
                        f.write(full_prompt + "".join(test) + open_brackets_count * "}")
                        counter += 1
                    test = []

                if "@Test" in line and not test_found:
                    test_found = True

                if test_found:
                    test.append(line)

    def _execute_tool_for_tests_generation(self, input_jar: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        class_name, methods = list(scenario.targets.items())[0]
         
        mpath = "/home/nfab/dist"
        lpath = "/home/nfab/dist/libs"
        model = "CodeLlama-7b-Instruct-hf-q4f16_1-MLC"
        lib = "CodeLlama-7b-Instruct-hf-q4f16_1-cuda.so"
        prompts_path = f"{output_path}/prompts.txt"

        code_base = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_base.java"
        code_left = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_left.java"
        code_right = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_right.java"
        code_merge = f"/mnt/c/Users/natha/Downloads/mergedataset/mergedataset/spring-boot/ea8107b6a53fa60b5f23b33e1b6d2e88bb60133c/source/UndertowEmbeddedServletContainerFactory_merge.java"

        code, branch = self.get_branch(input_jar, code_base, code_left, code_right, code_merge)

        self.generate_prompts(prompts_path, class_name, methods, code)
        imports = self.get_imports(code)

        prompts_list = self.read_prompts(prompts_path)
        
        cm = self.create_chat_module(mpath, lpath, model, lib)

        for i, prompt in enumerate(prompts_list):
            for j in range(0, 2):
                try:
                    print(f"----------------------------- Generating output {i}{j} in branch \"{branch}\" -----------------------------")
                    output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}"
                    output = self.generate_output(cm, prompt)
                    self.save_output(prompt, output, output_path, output_file_name)
                    self.reset_chat_module(cm)
                except Exception as e:
                    print(f"Error while generating output {i}-{j} in branch {branch}: {e}")
                    pass
            self.get_individual_tests(output_path, prompt, class_name, imports, i)