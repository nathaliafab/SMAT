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
            open_brackets_count = 0
            test_found = False
            test_signature = ""

            if file.endswith(".txt") and file.startswith(f"{i}"):
                with open(os.path.join(llm_outputs_path, file), "r") as f:
                    lines.extend(f.readlines())

            for j, line in enumerate(lines):
                if "{" in line:
                    open_brackets_count += 1
                
                if "}" in line:
                    open_brackets_count -= 1

                if ("@Test" in line or "import" in line or "package" in line) and test_found:
                    test_found = False
                    method_name = f"{class_name.split('.')[-1]}Test_{i}_{counter}"
                    with open(f"{output_path}/{method_name}.java", "w") as f:
                        new_prompt = prompt.split("public class")[0]
                        new_prompt += f"public class {method_name} {{\n"
                        full_prompt = "".join(imports) + new_prompt
                        f.write(full_prompt + "".join(test) + open_brackets_count * "}")
                        counter += 1
                    test = []

                if "@Test" in line and not test_found:
                    test_found = True
                    test_signature = lines[j+1].strip()

                if test_signature in line and test_found:
                    line = line.replace(test_signature, f"public void test{i}{counter}() {{")

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
            for j in range(0, 10):
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