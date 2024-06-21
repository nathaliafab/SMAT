import os, logging
from typing import List
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.test_suite_generator import \
    TestSuiteGenerator

from mlc_chat import ChatModule

class CodellamaTestSuiteGenerator(TestSuiteGenerator):

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
            class_fqcn = os.path.basename(class_path).replace(".java", "")
            class_names.append(class_fqcn)

        return class_names


    def get_method_code(self, file_path, method_name):
        with open(file_path, 'r') as file:
            lines = file.readlines()

        method_found = False
        method_code = []
        class_attributes = []
        current_method = []
        other_methods = []
        search_other_methods = False

        for line in lines:
            stripped_line = line.strip()
            
            # Check for class attributes
            if ';' in stripped_line and ('private' in stripped_line or 'public' in stripped_line):
                class_attributes.append(line)
            
            # Check for method definition
            if stripped_line.startswith(('private', 'public')) and method_name.split('(')[0] in stripped_line:
                method_found = True
                current_method = [line]
            elif method_found and stripped_line.startswith(('private', 'public')):
                break
            elif method_found:
                current_method.append(line)

        if method_found:
            method_code = current_method

            if search_other_methods:
                for line in method_code:
                    try:
                        method_call = line.split('.')[1].strip()
                        if '(' in line and ')' in line and '=' not in line and ';' in line and method_name not in line:
                            method_call = method_call.split(';')[0]
                            other_methods.append(method_call)
                    except IndexError:
                        continue

        return method_found, class_attributes, method_code, other_methods


    def generate_prompts(self, prompts_file, class_name, methods, code):
        for method in methods:
            try:
                method_found, class_attributes, method_code, other_methods = self.get_method_code(code, method)

                other_method_codes = []
                if method_found:
                    if other_methods:
                        for other_method in other_methods:
                            other_method_found, ca, other_method_code, om = self.get_method_code(code, other_method)

                            if other_method_found:
                                other_method_codes.append(other_method_code)

                    modified_lines = []
                    modified_lines.append(f"/*\n{''.join(class_attributes)}\n{''.join(method_code)}")
                    if other_methods:
                        modified_lines.append("\n")
                        for i in range(len(other_method_codes)):
                            modified_lines.append(f"{''.join(other_method_codes[i])}")
                    modified_lines.append("*/\n\n")
                    modified_lines.append("import org.junit.FixMethodOrder;\n")
                    modified_lines.append("import org.junit.Test;\n")
                    modified_lines.append("import org.junit.runners.MethodSorters;\n")
                    modified_lines.append("import static org.junit.Assert.*;\n\n")
                    modified_lines.append(f"@FixMethodOrder(MethodSorters.NAME_ASCENDING)\n")
                    modified_lines.append(f"public class {class_name.split('.')[-1]}_{method.split('(')[0]}Test {{\n")
                    modified_lines.append(f"//continue the test with code only:\n")
                    modified_lines.append(f"\"\"\"")
                
                    with open(prompts_file, "w") as file:
                        file.writelines(modified_lines)

            except Exception as e:
                logging.error("Error while generating prompt for method %s: %s", method, e)


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


    def reset_chat_module(self, chat_module):
        chat_module.reset_chat()


    def generate_output(self, chat_module, prompt):
        return chat_module.generate(prompt=prompt)


    def save_output(self, prompt, output, dir, output_file_name):
        if dir:
            if not os.path.exists(dir):
                os.makedirs(dir)
            if not os.path.exists(f"{dir}/llm_outputs"):
                os.makedirs(f"{dir}/llm_outputs")

        output_file_path = f"{dir}/llm_outputs/{output_file_name}.txt"
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


    def get_individual_tests(self, output_path, prompt, class_name, imports, i):
        counter = 0

        llm_outputs_path = f"{output_path}/llm_outputs/"

        for file in os.listdir(llm_outputs_path):
            lines = []
            test = []
            before = []
            open_brackets_count = 1
            test_found = False
            before_found = False
            test_signature = ""

            if file.endswith(".txt") and file.startswith(f"{i}"):
                with open(os.path.join(llm_outputs_path, file), "r") as f:
                    lines.extend(f.readlines())

            for j, line in enumerate(lines):
                if ("@Test" in line or "import" in line or "package" in line or not open_brackets_count) and test_found:
                    test_found = False
                    method_name = f"{class_name.split('.')[-1]}Test_{i}_{counter}"
                    with open(f"{output_path}/{method_name}.java", "w") as f:
                        new_prompt = prompt.split("public class")[0]
                        new_prompt += f"public class {method_name} {{\n"
                        full_prompt = "".join(imports) + new_prompt
                        if before:
                            full_prompt += "".join(before)
                        f.write(full_prompt + "".join(test) + open_brackets_count * "}")
                        counter += 1
                    test = []

                if "@Test" in line and not test_found:
                    test_found = True
                    before_found = False
                    if lines[j+1]:
                        test_signature = lines[j+1].strip()

                if before_found:
                    before.append(line)

                if ("@Before" in line and not before_found):
                    before_found = True
                    before.append(line)

                if test_found:
                    if test_signature in line:
                        line = line.replace(test_signature, f"public void test{i}{counter}() {{")

                    if "{" in line:
                        open_brackets_count += 1
                
                    if "}" in line:
                        open_brackets_count -= 1

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

        """
        code_base = f"/mnt/c/Users/natha/Downloads/smat/base.java"
        code_left = f"/mnt/c/Users/natha/Downloads/smat/left.java"
        code_right = f"/mnt/c/Users/natha/Downloads/smat/right.java"
        code_merge = f"/mnt/c/Users/natha/Downloads/smat/merge.java"
        """

        code, branch = self.get_branch(input_jar, code_base, code_left, code_right, code_merge)

        self.generate_prompts(prompts_path, class_name, methods, code)
        imports = self.get_imports(code)

        prompts_list = self.read_prompts(prompts_path)
        
        cm = self.create_chat_module(mpath, lpath, model, lib)

        for i, prompt in enumerate(prompts_list):
            for j in range(0, 5):
                try:
                    logging.debug("Generating output %d%d in branch \"%s\"", i, j, branch)
                    output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}"
                    output = self.generate_output(cm, prompt)
                    self.save_output(prompt, output, output_path, output_file_name)
                    self.reset_chat_module(cm)
                except Exception as e:
                    logging.error("Error while generating output %d%d in branch \"%s\": %s", i, j, branch, e)
                    pass
            self.get_individual_tests(output_path, prompt, class_name, imports, i)